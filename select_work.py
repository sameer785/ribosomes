import os
import glob
import ribosome_profiling_experiment
import simulate
import subprocess
import numpy as np
import visualize
import contaminants
from collections import Counter

def build_all_experiments(verbose=False):
    experiment_from_file_name = ribosome_profiling_experiment.RibosomeProfilingExperiment.from_description_file_name
    
    families = ['zinshteyn_plos_genetics',
                'ingolia_science',
                'weinberg',
                'dunn_elife',
                'gerashchenko_pnas',
                'gerashchenko_nar',
                'guydosh_cell',
                'mcmanus_gr',
                'artieri',
                'artieri_gr_2',
                'lareau_elife',
                'belgium_2015_03_16',
                'belgium_2014_12_10',
                'belgium_2014_10_27',
                'belgium_2014_08_07',
                'belgium_2014_03_05',
                'belgium_2013_08_06',
                'pop_msb',
                'gardin_elife',
                'brar_science',
                'baudin-baillieu_cell_reports',
                'nedialkova_cell',
                'jan_science',
                'williams_science',
                'sen_gr',
               ]

    experiments = {}
    for family in families:
        if verbose:
            print family
        experiments[family] = {}
        prefix = '{0}/projects/ribosomes/experiments/{1}/'.format(os.environ['HOME'], family)
        dirs = [path for path in glob.glob('{}*'.format(prefix)) if os.path.isdir(path)]
        for d in sorted(dirs):
            _, name = os.path.split(d)
            if verbose:
                print '\t', name
            description_file_name = '{0}/job/description.txt'.format(d)
            experiments[family][name] = experiment_from_file_name(description_file_name)

    return experiments

def build_all_simulation_experiments(verbose=False):
    experiment_from_file_name = simulate.SimulationExperiment.from_description_file_name
    
    experiments = {}
    prefix = '{0}/projects/ribosomes/experiments/simulation/'.format(os.environ['HOME'])
    dirs = [path for path in glob.glob('{}*'.format(prefix)) if os.path.isdir(path)]
    for d in sorted(dirs):
        _, name = os.path.split(d)
        if verbose:
            print '\t', name
        description_file_name = '{0}/job/description.txt'.format(d)
        experiments[name] = experiment_from_file_name(description_file_name)

    return experiments

def read_counts_and_RPKMS():
    experiments = build_all_experiments()
    for family in experiments:
        print family
        for name in experiments[family]:
            print '\t', name
            experiments[family][name].compute_total_read_counts()
            experiments[family][name].compute_RPKMs()

def package_files(key):
    prefix = '/home/jah/projects/ribosomes/'
    os.chdir(prefix)
    full_file_names = []
    package_file_name = 'all_{}.tar.gz'.format(key)

    experiments = build_all_experiments()
    for family in experiments:
        if 'belgium' in family:
            continue
        for name in experiments[family]:
            full_file_names.append(experiments[family][name].file_names[key])

    def strip_prefix(fn, prefix):
        if not fn.startswith(prefix):
            raise ValueError(fn)
        return fn[len(prefix):]

    relative_file_names = [strip_prefix(fn, prefix) for fn in full_file_names]
    tar_command = ['tar', '-czf', package_file_name] + relative_file_names
    subprocess.check_call(tar_command)

def make_counts_array_file(exclude_edges=False):
    prefix = '/home/jah/projects/ribosomes/'
    os.chdir(prefix)
    if exclude_edges:
        fn = 'all_read_counts_exclude_edges.txt'
    else:
        fn = 'all_read_counts.txt'
    read_counts = {}
    full_experiments = []
    experiments = build_all_experiments()
    for family in sorted(experiments):
        read_counts[family] = {}
        for name in sorted(experiments[family]):
            full_experiment = '{0}:{1}'.format(family, name)
            full_experiments.append(full_experiment)
            if exclude_edges:
                read_counts[family][name] = experiments[family][name].read_file('read_counts_exclude_edges')
            else:
                read_counts[family][name] = experiments[family][name].read_file('read_counts')

    gene_names = sorted(read_counts[family][name].keys())
    gene_lengths = [read_counts[family][name][gene_name]['CDS_length'] for gene_name in gene_names]

    full_array = [gene_lengths]

    for full_experiment in full_experiments:
        family, name = full_experiment.split(':')
        counts = [read_counts[family][name][gene_name]['expression'][0] for gene_name in gene_names]
        full_array.append(counts)

    full_array = np.asarray(full_array).T

    with open(fn, 'w') as fh:
        fh.write('name\tlength\t{0}\n'.format('\t'.join(full_experiments)))
        for gene_name, row in zip(gene_names, full_array):
            fh.write('{0}\t'.format(gene_name))
            fh.write('{0}\n'.format('\t'.join(map(str, row))))

def make_restricted_starts_and_ends_plots():
    all_experiments = build_all_experiments(verbose=False)

    relevant_lengths = range(19, 25)
    for name in all_experiments['gerashchenko_pnas']:
        if 'rep1' in name and 'foot' in name and 'Initial' not in name:
            print name
            experiment = all_experiments['gerashchenko_pnas'][name]
            #experiment.plot_starts_and_ends()
            experiment.plot_mismatch_types()
            #position_counts = experiment.read_file('from_starts_and_ends')
            #visualize.plot_metagene_positions(position_counts['from_starts'],
            #                                  position_counts['from_ends'],
            #                                  experiment.figure_file_names['starts_and_ends'],
            #                                  relevant_lengths=relevant_lengths,
            #                                 )
            #visualize.plot_metacodon_positions(position_counts['from_starts'],
            #                                   experiment.figure_file_names['starts_and_ends'],
            #                                   key='start_codon',
            #                                  )

def make_mismatch_position_plots():
    all_experiments = build_all_experiments(verbose=False)

    for group in all_experiments:
        if 'belgium' not in group:
            continue
        print group
        for name in all_experiments[group]:
            if 'jeff' in name:
                continue
            print '\t', name
            experiment = all_experiments[group][name]
            #experiment.plot_mismatches()
            experiment.plot_starts_and_ends()

def make_multipage_pdf(figure_name):
    all_experiments = build_all_experiments(verbose=False)
    all_fn = '/home/jah/projects/ribosomes/results/gerashchenko_{0}.pdf'.format(figure_name)
    fns = []
    for name in sorted(all_experiments['gerashchenko_nar'], key=gerashchenko_nar_sorting_key):
        print name
        fns.append(all_experiments['gerashchenko_nar'][name].figure_file_names[figure_name])

    pdftk_command = ['pdftk'] + fns + ['cat', 'output', all_fn]
    subprocess.check_call(pdftk_command)

def get_read_lengths():
    all_experiments = build_all_experiments(verbose=False)
    read_lengths = Counter()
    for group in sorted(all_experiments):
        for name in sorted(all_experiments[group]):
            experiment = all_experiments[group][name]
            read_lengths[experiment.max_read_length] += 1
            if experiment.max_read_length == 76:
                print group, name
    print read_lengths.most_common()

def gerashchenko_nar_sorting_key(name):
    num, denom, rep = gerashchenko_fraction(name)
    concentration = float(num) / float(denom)

    return concentration, rep

def gerashchenko_fraction(name):
    _, concentration = name.split('_', 1)
    concentration, rep = concentration.split('CHX')
    rep = rep.lstrip('_')

    if concentration == 'no':
        num, denom = 0, 1
    else:
        concentration = concentration.strip('_x')
        if '_' in concentration:
            num, denom = concentration.split('_')
        else:
            num, denom = int(concentration), 1

    return num, denom, rep

def get_gerashchenko_nar_experiments(series='unstressed'):
    experiments = build_all_experiments(verbose=False)
    relevant_exps = [exp for exp in experiments['gerashchenko_nar'].values() if series in exp.name]
    sorted_exps = sorted(relevant_exps, key=lambda exp: gerashchenko_nar_sorting_key(exp.name))
    return sorted_exps

def make_averaged_codon_densities_plot():
    experiments = build_all_experiments(verbose=False)
    
    def transform(experiment):
        _, concentration = experiment.name.split('_', 1)
        concentration, _ = concentration.split('CHX')
        if concentration == 'no':
            concentration = 0
        else:
            concentration = concentration.strip('_x')
            if '_' in concentration:
                num, denom = concentration.split('_')
                concentration = float(num) / float(denom)
            else:
                concentration = int(concentration)

        return concentration

    sorted_experiments = sorted(experiments['gerashchenko_nar'].values(), key=transform)
    data_sets = [(experiment.name, experiment.read_file('mean_densities'), i)
                 for i, experiment in enumerate(sorted_experiments)]

    visualize.plot_averaged_codon_densities(data_sets,
                                            'test.pdf',
                                            past_edge=10,
                                            plot_up_to=100,
                                            show_end=True,
                                           )

def make_rRNA_coverage_plot():
    colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k'] * 10
    experiments = build_all_experiments(verbose=False)
    all_experiments = [exp for exp in experiments['belgium_2014_08_07'].values() if 'FP' in exp.name]

    coverage_data = {exp.name: (exp.get_total_reads(), exp.read_file('rRNA_coverage'), color)
                     for exp, color in zip(all_experiments, colors)}

    contaminants.plot_rRNA_coverage(coverage_data,
                                    all_experiments[0].file_names['oligos_sam'],
                                    'belgium_2014_08_07_rRNA_coverage_{0}.pdf',
                                   )

def load_all_enrichments():
    weinberg_names = ['RPF']

    arlen_names = ['WT_1_FP',
                   'WT_2_FP',
                   'R98S_1_FP',
                   'R98S_2_FP',
                  ]
    old_arlen_names = ['WT_cDNA_sample',
                       'R98S_cDNA_sample',
                       'Suppressed_R98S_cDNA_sample',
                      ]

    guydosh_names = ['wild-type_CHX',
                     'wild-type_no_additive',
                    ]

    gardin_names = ['ribosome_footprints_for_wildtype']

    experiments = build_all_experiments()
    relevant_experiments = get_gerashchenko_nar_experiments('unstressed') + \
                           get_gerashchenko_nar_experiments('oxidative') + \
                           get_gerashchenko_nar_experiments('heat') + \
                           [experiments['weinberg'][name] for name in weinberg_names] + \
                           [experiments['belgium_2014_12_10'][name] for name in arlen_names] + \
                           [experiments['belgium_2013_08_06'][name] for name in old_arlen_names] + \
                           experiments['dunn_elife'].values() + \
                           [experiments['artieri_gr_2']['non_multiplexed']] + \
                           experiments['zinshteyn_plos_genetics'].values() + \
                           experiments['pop_msb'].values() + \
                           experiments['mcmanus_gr'].values() + \
                           experiments['brar_science'].values() + \
                           experiments['lareau_elife'].values() + \
                           experiments['nedialkova_cell'].values() + \
                           [experiments['gardin_elife'][name] for name in gardin_names] + \
                           [v for n, v in experiments['ingolia_science'].items() if 'Footprint' in n] + \
                           [experiments['guydosh_cell'][name] for name in guydosh_names] + \
                           [v for n, v in experiments['gerashchenko_pnas'].items() if 'foot' in n] + \
                           experiments['jan_science'].values() + \
                           experiments['williams_science'].values()
            
    enrichments = {exp.name: exp.read_file('stratified_mean_enrichments') for exp in relevant_experiments}

    representatives = {'belgium_2014_12_10': 'WT_2_FP',
                       'ingolia': 'Footprints-rich-1',
                       'brar': 'footprints_for_exponential_vegetative_cells_of_the_strain_gb15_used_for_the_traditional_timecourse',
                       'gerashchenko pnas': 'Initial_rep1_foot',
                       'dunn': 'dunn_elife',
                       'artieri': 'non_multiplexed',
                       'mcmanus': 'S._cerevisiae_Ribo-seq_Rep_1',
                       'zinshteyn': 'WT_Ribosome_Footprint_1',
                       'lareau +': 'Cycloheximide_replicate_1',
                       'nedialkova +': 'WT_ribo_YPD_rep1',
                       'jan +': 'sec63mVenusBirA_+CHX_7minBiotin_input',
                       'williams +': 'Om45mVenusBirA_+CHX_2minBiotin_input',
                       'guydosh -': 'wild-type_CHX',
                       'weinberg': 'RPF',
                       'pop': 'WT_footprint',
                       'lareau -': 'Untreated_replicate_1',
                       'gardin': 'ribosome_footprints_for_wildtype',
                       'nedialkova -': 'WT_ribo_YPD_noCHX_rep1',
                       'jan -': 'sec63mVenusBirA_-CHX_7minBiotin_input',
                       'williams -': 'Om45mVenusBirA_-CHX_2minBiotin_input',
                      }

    for name in representatives:
        enrichments[name] = enrichments[representatives[name]]

    return enrichments
