import matplotlib
matplotlib.use('Agg', warn=False)
import matplotlib.pyplot as plt
import trim
import os
import pysam
import glob
from collections import Counter
from itertools import izip
from Sequencing import fastq, utilities, mapping_tools, sam, genomes
from Sequencing.annotation import Annotation_factory
from Sequencing.Parallel import map_reduce, split_file
from Sequencing.Serialize import array_1d, array_2d, counts, sparse_joint_counts
from Serialize import read_positions
from Sequencing.utilities import counts_to_array
import TIF_seq_structure
import rna_experiment
import positions
import visualize

orientations = ['R1_forward', 'R1_reverse', 'R2_forward', 'R2_reverse']

class TIFSeqExperiment(rna_experiment.RNAExperiment):
    num_stages = 2

    specific_results_files = [
        ('five_prime_boundaries', 'fastq', '{name}_five_prime_boundaries.fastq'),
        ('three_prime_boundaries', 'fastq', '{name}_three_prime_boundaries.fastq'),
        ('R1_forward_positions', array_1d, '{name}_R1_forward_positions.txt'),
        ('R1_reverse_positions', array_1d, '{name}_R1_reverse_positions.txt'),
        ('R2_forward_positions', array_1d, '{name}_R2_forward_positions.txt'),
        ('R2_reverse_positions', array_1d, '{name}_R2_reverse_positions.txt'),
        ('polyA_lengths', array_1d, '{name}_polyA_lengths.txt'),
        ('joint_lengths', array_2d, '{name}_joint_lengths.txt'),
        ('id_counts', counts, '{name}_id_counts.txt'),

        ('five_prime_tophat_dir', 'dir', 'tophat_five_prime'),
        ('five_prime_accepted_hits', 'bam', 'tophat_five_prime/accepted_hits.bam'),
        ('five_prime_unmapped', 'bam', 'tophat_five_prime/unmapped.bam'),

        ('three_prime_tophat_dir', 'dir', 'tophat_three_prime'),
        ('three_prime_accepted_hits', 'bam', 'tophat_three_prime/accepted_hits.bam'),
        ('three_prime_unmapped', 'bam', 'tophat_three_prime/unmapped.bam'),

        ('combined_extended', 'bam', '{name}_combined_extended.bam'),
        
        ('nongenomic_lengths', array_1d, '{name}_nongenomic_lengths.txt'),

        ('joint_positions', sparse_joint_counts, '{name}_joint_positions.txt'),
    ]

    specific_figure_files = [
        ('positions', '{name}_positions.pdf'),
        ('polyA_lengths', '{name}_polyA_lengths.pdf'),
    ]

    specific_outputs = [
        ['R1_forward_positions',
         'R1_reverse_positions',
         'R2_forward_positions',
         'R2_reverse_positions',
         'polyA_lengths',
         'id_counts',
         'joint_lengths',
         'combined_extended',
        ],
        ['read_positions',
         'metagene_positions',
         'joint_positions',
        ],
    ]

    specific_work = [
        [#'extract_boundary_sequences',
         #'map_tophat',
         'combine_mappings',
        ],
        ['get_read_positions',
         'get_metagene_positions',
        ],
    ]

    specific_cleanup = [
        ['plot_positions',
         'plot_polyA_lengths',
        ],
        ['plot_starts_and_ends',
        ],
    ]

    def __init__(self, **kwargs):
        super(TIFSeqExperiment, self).__init__(**kwargs)

        self.min_payload_length = 12
        
    def trim_barcodes(self, read_pairs):
        num_to_trim = len(TIF_seq_structure.barcodes['mp1'])

        def trim_read(read):
            trimmed = fastq.Read(read.name,
                                 read.seq[num_to_trim:],
                                 read.qual[num_to_trim:],
                                )
            return trimmed

        for R1, R2 in read_pairs:
            yield trim_read(R1), trim_read(R2)

    def extract_boundary_sequences(self):
        read_pairs = self.get_read_pairs()
        trimmed_read_pairs = self.trim_barcodes(read_pairs)

        total_reads = 0
        well_formed = 0
        long_enough = 0
    
        counters = {'positions': {orientation: Counter() for orientation in orientations},
                    'control_ids': Counter(),
                    'polyA_lengths': Counter(),
                    'left_ids': Counter(),
                    'right_ids': Counter(),
                    'joint_lengths': Counter(),
                   }

        with open(self.file_names['five_prime_boundaries'], 'w') as fives_fh, \
             open(self.file_names['three_prime_boundaries'], 'w') as threes_fh:

            for R1, R2 in trimmed_read_pairs:
                total_reads += 1
                five_payload_read, three_payload_read = TIF_seq_structure.find_boundary_sequences(R1, R2, counters)
                if five_payload_read and three_payload_read:
                    well_formed += 1
                    if len(five_payload_read.seq) >= self.min_payload_length and \
                       len(three_payload_read.seq) >= self.min_payload_length:
                        long_enough += 1
                        fives_fh.write(fastq.make_record(*five_payload_read))
                        threes_fh.write(fastq.make_record(*three_payload_read))

        # Pop off of counters so that what is left at the end can be written
        # directly to the id_counts file.
        position_counts = counters.pop('positions')
        for orientation in orientations:
            key = '{0}_{1}'.format(orientation, 'positions')
            array = counts_to_array(position_counts[orientation])
            self.write_file(key, array)

        polyA_lengths = counts_to_array(counters.pop('polyA_lengths'))
        self.write_file('polyA_lengths', polyA_lengths)

        joint_lengths = counts_to_array(counters.pop('joint_lengths'), dim=2)
        self.write_file('joint_lengths', joint_lengths)
        
        self.write_file('id_counts', counters)

        self.summary.extend(
            [('Total read pairs', total_reads),
             ('Well-formed', well_formed),
             ('Long enough', long_enough),
            ],
        )

    def map_tophat(self):
        mapping_tools.map_tophat([self.file_names['five_prime_boundaries']],
                                 self.file_names['bowtie2_index_prefix'],
                                 self.file_names['genes'],
                                 self.file_names['transcriptome_index'],
                                 self.file_names['five_prime_tophat_dir'],
                                 no_sort=True,
                                )

        mapping_tools.map_tophat([self.file_names['three_prime_boundaries']],
                                 self.file_names['bowtie2_index_prefix'],
                                 self.file_names['genes'],
                                 self.file_names['transcriptome_index'],
                                 self.file_names['three_prime_tophat_dir'],
                                 no_sort=True,
                                )

    def combine_mappings(self):
        num_unmapped = 0
        num_five_unmapped = 0
        num_three_unmapped = 0
        num_nonunique = 0
        num_discordant = 0
        num_concordant = 0

        five_prime_mappings = pysam.Samfile(self.file_names['five_prime_accepted_hits'])
        five_prime_unmapped = pysam.Samfile(self.file_names['five_prime_unmapped'])
        all_five_prime = sam.merge_by_name(five_prime_mappings, five_prime_unmapped)
        five_prime_grouped = utilities.group_by(all_five_prime, lambda m: m.qname)

        three_prime_mappings = pysam.Samfile(self.file_names['three_prime_accepted_hits'])
        three_prime_unmapped = pysam.Samfile(self.file_names['three_prime_unmapped'])
        all_three_prime = sam.merge_by_name(three_prime_mappings, three_prime_unmapped)
        three_prime_grouped = utilities.group_by(all_three_prime, lambda m: m.qname)

        group_pairs = izip(five_prime_grouped, three_prime_grouped)

        alignment_sorter = sam.AlignmentSorter(five_prime_mappings.references,
                                               five_prime_mappings.lengths,
                                               self.file_names['combined_extended'],
                                              )
        region_fetcher = genomes.build_region_fetcher(self.file_names['genome'],
                                                      load_references=True,
                                                      sam_file=five_prime_mappings,
                                                     )

        with alignment_sorter:
            for (five_qname, five_group), (three_qname, three_group) in group_pairs:
                five_annotation = trim.PayloadAnnotation.from_identifier(five_qname)
                three_annotation = trim.PayloadAnnotation.from_identifier(three_qname)
                if five_annotation['original_name'] != three_annotation['original_name']:
                    # Ensure that the iteration through pairs is in sync.
                    print five_qname, three_qname
                    raise ValueError

                five_unmapped = any(m.is_unmapped for m in five_group)
                three_unmapped = any(m.is_unmapped for m in three_group)
                if five_unmapped:
                    num_five_unmapped += 1
                if three_unmapped:
                    num_three_unmapped += 1
                if five_unmapped or three_unmapped:
                    num_unmapped += 1
                    continue

                five_nonunique = len(five_group) > 1 or any(m.mapq < 40 for m in five_group)
                three_nonunique = len(three_group) > 1 or any(m.mapq < 40 for m in three_group)
                if five_nonunique or three_nonunique:
                    num_nonunique += 1
                    continue
                
                five_m = five_group.pop()
                three_m = three_group.pop()

                five_strand = '-' if five_m.is_reverse else '+'
                three_strand = '-' if three_m.is_reverse else '+'

                tlen = max(five_m.aend, three_m.aend) - min(five_m.pos, three_m.pos)
                discordant = (five_m.tid != three_m.tid) or (five_strand) != (three_strand) or (tlen > 10000) 
                if discordant:
                    num_discordant += 1
                    continue
                
                if five_strand == '+':
                    first_read = five_m
                    second_read = three_m
                elif five_strand == '-':
                    first_read = three_m
                    second_read = five_m
                
                gap = second_read.pos - first_read.aend
                if gap < 0:
                    num_discordant += 1
                    continue
                
                combined_read = pysam.AlignedRead()
                # qname needs to come from three_m to include trimmed As
                combined_read.qname = three_m.qname
                combined_read.tid = five_m.tid
                combined_read.seq = first_read.seq + second_read.seq
                combined_read.qual = first_read.qual + second_read.qual
                combined_read.cigar = first_read.cigar + [(3, gap)] + second_read.cigar
                combined_read.pos = first_read.pos
                combined_read.is_reverse = first_read.is_reverse
                combined_read.mapq = min(first_read.mapq, second_read.mapq)
                combined_read.rnext = -1
                combined_read.pnext = -1
                
                num_concordant += 1

                extended_mapping = trim.extend_polyA_end(combined_read,
                                                         region_fetcher,
                                                        )

                alignment_sorter.write(extended_mapping)

        self.summary.extend(
            [('Unmapped', num_unmapped),
             ('Five prime unmapped', num_five_unmapped),
             ('Three prime unmapped', num_three_unmapped),
             ('Nonunique', num_nonunique),
             ('Discordant', num_discordant),
             ('Concordant', num_concordant),
            ],
        )

    def get_read_positions(self):
        piece_CDSs, max_gene_length = self.get_CDSs()
        gene_infos = positions.get_Transcript_position_counts(self.merged_file_names['combined_extended'],
                                                              piece_CDSs,
                                                              [],
                                                              left_buffer=500,
                                                              right_buffer=500,
                                                             )

        self.read_positions = {}
        for name, info in gene_infos.iteritems():
            five_prime_counts = info['five_prime_positions']
            three_prime_counts = info['three_prime_positions']
            
            all_positions = {'all': five_prime_counts['all'],
                             'three_prime_genomic': three_prime_counts[0],
                             'three_prime_nongenomic': three_prime_counts['all'] - three_prime_counts[0],
                             'sequence': info['sequence'],
                            }
            self.read_positions[name] = all_positions

        self.write_file('read_positions', self.read_positions)

        joint_position_counts = {}
        for transcript in piece_CDSs:
            counts = positions.get_joint_position_counts_sparse(self.merged_file_names['combined_extended'],
                                                                transcript,
                                                                left_buffer=500,
                                                                right_buffer=500,
                                                               )
            joint_position_counts[transcript.name] = counts

        self.write_file('joint_positions', joint_position_counts)

    def get_metagene_positions(self):
        piece_CDSs, max_gene_length = self.get_CDSs()

        read_positions = self.load_read_positions()

        metagene_positions = positions.compute_metagene_positions(piece_CDSs,
                                                                  read_positions,
                                                                  max_gene_length,
                                                                 )
        self.write_file('metagene_positions', metagene_positions)
    
    def plot_starts_and_ends(self):
        metagene_positions = self.read_file('metagene_positions')

        visualize.plot_metagene_positions(metagene_positions,
                                          self.figure_file_names['starts_and_ends'],
                                          ['five_prime', 'three_prime_genomic', 'three_prime_nongenomic'],
                                         )
        
    def plot_positions(self):
        fig, ax = plt.subplots()

        max_length = 0
        for orientation in orientations:
            key = '{0}_positions'.format(orientation)
            array = self.read_file(key)
            max_length = max(max_length, len(array))
            ax.plot(array, '.-', label=orientation)

        ax.set_xlim(right=max_length - 1)
        ax.legend(loc='upper right', framealpha=0.5)
        fig.savefig(self.figure_file_names['positions'])

    def plot_polyA_lengths(self):
        fig, ax = plt.subplots()

        array = self.read_file('polyA_lengths')
        ax.plot(array, '.-', label='polyA_lengths')

        ax.legend(loc='upper right', framealpha=0.5)
        fig.savefig(self.figure_file_names['polyA_lengths'])


    def get_joint_position_counts(self, gene_name):
        CDSs, _ = self.get_CDSs()
        CDS_dict = {t.name: t for t in CDSs}
        transcript = CDS_dict[gene_name]

        joint_position_counts = positions.get_joint_position_counts_sparse(self.file_names['combined_extended_sorted'],
                                                                           transcript,
                                                                          )
        return joint_position_counts, transcript

    def get_total_eligible_reads(self):
        summary_pairs = self.read_file('summary')
        summary_dict = {name: values[0] for name, values in summary_pairs}
        total_mapped_reads = summary_dict['Nonunique'] + summary_dict['Concordant']
        return total_mapped_reads

if __name__ == '__main__':
    script_path = os.path.realpath(__file__)
    map_reduce.controller(TIFSeqExperiment, script_path)
