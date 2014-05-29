import matplotlib
matplotlib.use('Agg', warn=False)
import matplotlib.pyplot as plt
import positions
import numpy as np
import brewer2mpl
    
bmap = brewer2mpl.get_map('Set1', 'qualitative', 9)
colors = bmap.mpl_colors[:5] + bmap.mpl_colors[6:] + ['black']
colors = colors + colors

def smoothed(position_counts, window_size):
    smoothed_array = positions.PositionCounts(position_counts.extent_length,
                                              position_counts.left_buffer,
                                              position_counts.right_buffer,
                                              counts=position_counts.counts,
                                             )
    for i in range(window_size):
        smoothed_array[i] = position_counts[:i + 1].sum() / float(i + 1)
    for i in range(window_size, smoothed_array.extent_length - window_size):
        smoothed_array[i] = position_counts[i - window_size:i + window_size + 1].sum() / float(2 * window_size + 1)
    for i in range(smoothed_array.extent_length - window_size, smoothed_array.extent_length):
        smoothed_array[i] = position_counts[i:].sum() / float(smoothed_array.extent_length - i)
    return smoothed_array

def plot_metagene_positions(from_starts, from_ends, figure_fn, zoomed_out=False):
    relevant_lengths = sorted(from_starts.keys())
    fig, (start_ax, end_ax) = plt.subplots(2, 1, figsize=(12, 16))

    if zoomed_out:
        start_xs = np.arange(-100, 140)
        end_xs = np.arange(-190, 140)
    else:
        start_xs = np.arange(-21, 19)
        end_xs = np.arange(-6, 34)

    for length in relevant_lengths:
        start_ax.plot(start_xs, from_starts[length][start_xs], '.-', label=length)
        end_ax.plot(-end_xs, from_ends[length].relative_to_end[end_xs], '.-', label=length)

    start_ax.set_xlim(min(start_xs), max(start_xs))
    mod_3 = [x for x in start_xs if x % 3 == 0]
    mod_30 = [x for x in start_xs if x % 30 == 0]
    if zoomed_out:
        xticks = mod_30
    else:
        xticks = mod_3
    start_ax.set_xticks(xticks)
    for x in xticks:
        start_ax.axvline(x, color='black', alpha=0.1)
    start_ax.set_xlabel('Position of read relative to start of CDS')
    start_ax.set_ylabel('Number of uniquely mapped reads of specified length')
    
    end_ax.set_xlim(min(-end_xs), max(-end_xs))
    mod_3 = [x for x in -end_xs if x % 3 == 0]
    mod_30 = [x for x in -end_xs if x % 30 == 0]
    if zoomed_out:
        xticks = mod_30
    else:
        xticks = mod_3
    end_ax.set_xticks(xticks)
    for x in xticks:
        end_ax.axvline(x, color='black', alpha=0.1)
    end_ax.set_xlabel('Position of read relative to stop codon')
    end_ax.set_ylabel('Number of uniquely mapped reads of specified length')

    start_ax.legend(loc='upper right', framealpha=0.5)
    end_ax.legend(loc='upper right', framealpha=0.5)

    ymax = max(start_ax.get_ylim()[1], end_ax.get_ylim()[1])
    start_ax.set_ylim(0, ymax)
    end_ax.set_ylim(0, ymax)
    
    fig.savefig(figure_fn)

def plot_frames(from_starts, figure_fn):
    ''' Plots bar graphs of the distribution of reading frame that the 5' end of
        reads fell, stratified by read length.
    '''
    def bar_plot(values, name, tick_labels, ax):
        N = len(values)

        starts = np.arange(N)
        gap = 1 # in multiples of bar width

        width = 1. / (1 + gap)

        ax.bar(starts, values, width, label=name)

        ax.set_xlim(xmin=-width / 2, xmax=N - width / 2)

        ax.set_xticks(starts + (width * 1 / 2))
        ax.set_xticklabels(tick_labels)
        ax.xaxis.set_ticks_position('none')
        ax.set_ylim(0, 1)

        leg = ax.legend(loc='upper right', fancybox=True)
        leg.get_frame().set_alpha(0.5)

    relevant_lengths = sorted(from_starts.keys())
    extent_length = from_starts[relevant_lengths[0]].extent_length
    fig, axs = plt.subplots(len(relevant_lengths), 1, figsize=(6, 3 * len(relevant_lengths)))

    for length, ax in zip(relevant_lengths, axs):
        frames = np.zeros(3, int)
        for p in range(-15, extent_length):
            frames[p % 3] += from_starts[length][p]

        frames = np.true_divide(frames, frames.sum())

        tick_labels = ['0', '1', '2']

        bar_plot(frames, str(length), tick_labels, ax)
        
    axs[-1].set_xlabel('Frame')
    axs[len(axs) // 2].set_ylabel('Fraction of uniquely mapped reads of specified length')

    fig.savefig(figure_fn)

def plot_averaged_codon_densities(data_sets,
                                  figure_fn,
                                  show_end=True,
                                  past_edge=positions.codon_buffer,
                                  smooth=False,
                                  plot_up_to=100,
                                 ):
    if show_end:
        fig, (start_ax, end_ax) = plt.subplots(1, 2, figsize=(12, 8))
    else:
        fig, start_ax = plt.subplots(figsize=(12, 8))

    start_xs = np.arange(-past_edge, plot_up_to + 1)
    end_xs = np.arange(-past_edge + 1, plot_up_to + 1)

    for name, mean_densities, color_index in data_sets:
        densities = mean_densities['from_start']['codons']
        if smooth:
            densities = smoothed(densities, 5)
        start_densities = densities[start_xs]

        marker = '' if smooth else '.'
        linewidth = 2 if smooth else 1

        start_ax.plot(start_xs,
                      start_densities,
                      '.-',
                      label=name,
                      color=colors[color_index],
                      marker=marker,
                      linewidth=linewidth,
                     )
        if show_end:
            densities = mean_densities['from_end']['codons']
            if smooth:
                densities = smoothed(densities, 5)
            end_densities = densities.relative_to_end[end_xs]
            end_ax.plot(-end_xs,
                        end_densities,
                        '.-',
                        label=name,
                        color=colors[color_index],
                        marker=marker,
                        linewidth=linewidth,
                       )
    
    if len(data_sets) > 1:
        start_ax.legend(loc='upper right', framealpha=0.5)

    start_ax.set_xlabel('Number of codons from start codon')
    start_ax.set_ylabel('Mean normalized read density')
    start_ax.set_xlim(min(start_xs), max(start_xs))
    start_ax.plot(start_xs, [1 for x in start_xs], color='black', alpha=0.5)
   
    if show_end:
        end_ax.set_xlabel('Number of codons from stop codon')
        end_ax.yaxis.tick_right()
        end_ax.set_xlim(min(-end_xs), max(-end_xs))
        end_ax.plot(-end_xs, [1 for x in end_xs], color='black', alpha=0.5)
    
    axs = [start_ax]
    if show_end:
        axs.append(end_ax)

    ymax = max(ax.get_ylim()[1] for ax in axs)
    
    for ax in axs:
        ax.set_ylim(0, ymax + 0.1)
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
        ax.set_aspect((xmax - xmin) / (ymax - ymin))
        #ax.set_aspect(1)

    fig.set_size_inches(12, 12)
    fig.savefig(figure_fn, bbox_inches='tight')

def plot_metacodon_counts(metacodon_counts, fig_fn, codon_ids='all', enrichment=False, keys_to_plot=['actual']):
    random_counts = metacodon_counts['TTT'].itervalues().next()
    xs = np.arange(-random_counts.left_buffer, random_counts.extent_length)

    bases = 'TCAG'

    def make_plot(ax, codon_id):
        ax.set_title(codon_id)

        if codon_id not in metacodon_counts:
            return

        if enrichment:
            average_enrichment = metacodon_counts[codon_id]['sum_of_enrichments'] / metacodon_counts[codon_id]['num_eligible']
            ones = np.ones(len(average_enrichment.counts))
            ax.plot(xs, average_enrichment.counts, 'o-')
            ax.plot(xs, ones, color='black', alpha=0.5)
        else:
            for key in keys_to_plot:
                counts = metacodon_counts[codon_id][key].counts
                line, = ax.plot(xs, counts, '.-', label=key)
                if isinstance(key, int):
                    # -key + 1 is the position a read starts at if position 0
                    # is the last base in it
                    ax.axvline(-key + 1, color=line.get_color(), alpha=0.2)
            #ax.plot(xs, metacodon_counts[codon_id]['uniform'].counts, '.-')
            ax.ticklabel_format(axis='y', style='sci', scilimits=(0, 3))
            if codon_ids != 'all':
                ax.legend(loc='upper right', framealpha=0.5)

        ax.set_ylim(ymin=0)
        ax.set_xlim(min(xs), max(xs))
        ax.axvline(0, ls='--', color='black', alpha=0.5)
    
    if codon_ids == 'all':
        fig, axs = plt.subplots(16, 4, figsize=(16, 64))

        for first in range(4):
            for second in range(4):
                for third in range(4):
                    i = first * 4 + third
                    j = second
                    codon_id = ''.join(bases[first] + bases[second] + bases[third])
                    make_plot(axs[i, j], codon_id)
    else:
        fig, axs = plt.subplots(len(codon_ids), 1, figsize=(8, 8 * len(codon_ids)))
        for codon_id, ax in zip(codon_ids, axs):
            make_plot(ax, codon_id)

    fig.savefig(fig_fn, bbox_inches='tight')

def plot_single_length_metacodon_counts(metacodon_counts, fig_fn, codon_ids, length=28, edge="5'"):
    random_codon_id = metacodon_counts.iterkeys().next()
    random_counts = metacodon_counts[random_codon_id].itervalues().next()
    keys = metacodon_counts[random_codon_id].keys()
    xs = np.arange(-20, 20)

    bases = 'TCAG'

    def make_plot(ax, codon_id):
        ax.set_title(codon_id)

        if codon_id not in metacodon_counts:
            return

        counts = metacodon_counts[codon_id][length]
        if edge == "3'":
            positions = xs - length + 1
        else:
            positions = xs
        line, = ax.plot(xs, counts[positions], '.-')
        ax.ticklabel_format(axis='y', style='sci', scilimits=(0, 3))

        ax.set_ylim(ymin=0)
        ax.set_xlim(min(xs), max(xs))
        ax.axvline(0, ls='--', color='black', alpha=0.5)
    
    if codon_ids == 'all':
        fig, axs = plt.subplots(16, 4, figsize=(16, 64))

        for first in range(4):
            for second in range(4):
                for third in range(4):
                    i = first * 4 + third
                    j = second
                    codon_id = ''.join(bases[first] + bases[second] + bases[third])
                    make_plot(axs[i, j], codon_id)
    else:
        fig, axs = plt.subplots(len(codon_ids), 1, figsize=(8, 8 * len(codon_ids)))
        for codon_id, ax in zip(codon_ids, axs):
            make_plot(ax, codon_id)

    fig.suptitle('Read counts around every occurence, {0}'.format(edge))
    fig.savefig(fig_fn, bbox_inches='tight')

def plot_frameshifts(rpf_counts_list,
                     position_ambiguity_list,
                     edge_overlap,
                     gene_name,
                     gene_length,
                     exp_name,
                    ):
    ambiguity_to_color = {0: 'red',
                          1: 'green',
                          2: 'black',
                         }

    length_data = zip([28, 29, 30], rpf_counts_list, position_ambiguity_list)
    for fragment_length, rpf_counts, position_ambiguity in length_data:
        start_at_codon = 0 
        # codon_starts[i] is the index into a position array at which codon i
        # starts.
        codon_starts = np.arange(2 * edge_overlap + (start_at_codon * 3),
                                 2 * edge_overlap + gene_length,
                                 3,
                                )
        codon_numbers = start_at_codon + np.arange(len(codon_starts))
        
        # frame_counts_list[i, j] will be the number of RPF's starting at frame i of
        # codon j
        frame_counts_list = np.zeros((3, len(codon_starts)), int)
        # frame_colors_list will be used to visualize the ambiguity of each position
        frame_colors_list = [['']*len(codon_starts) for frame in range(3)]

        for c, codon_start in enumerate(codon_starts):
            for frame in range(3):
                frame_counts_list[frame, c] = rpf_counts[codon_start + frame]
                ambiguity = position_ambiguity[codon_start + frame]
                frame_colors_list[frame][c] = ambiguity_to_color[ambiguity]

        frames_so_far = frame_counts_list.cumsum(axis=1)
        fraction_frames_so_far = np.true_divide(frames_so_far, frames_so_far.sum(axis=0))

        frames_remaining = np.fliplr(np.fliplr(frame_counts_list).cumsum(axis=1))
        fraction_frames_remaining = np.true_divide(frames_remaining, frames_remaining.sum(axis=0))
        
        fig, axs = plt.subplots(4, 1, sharex=True)
        cumulative_ax = axs[0]
        frame_axs = axs[1:]

        for frame, (ax, frame_counts, frame_colors) in enumerate(zip(frame_axs, frame_counts_list, frame_colors_list)):
            ax.scatter(codon_numbers, frame_counts, s=20, c=frame_colors, linewidths=0)
            ax.set_ylim(-1, frame_counts_list.max() + 1)
            ax.set_xlim(codon_numbers[0], codon_numbers[-1])
            ax.set_title('Frame {0}'.format(frame))

        for frame, so_far, remaining, color in zip([0, 1, 2], fraction_frames_so_far, fraction_frames_remaining, colors):
            cumulative_ax.plot(codon_numbers, so_far, color=color, label='{0} so far'.format(frame))
            cumulative_ax.plot(codon_numbers, remaining, color=color, linestyle='--', label='{0} remaining'.format(frame))
            #difference = so_far - remaining
            #cumulative_ax.plot(codon_numbers, difference, color=color, linestyle=':')
            #difference = remaining - so_far
            #cumulative_ax.plot(codon_numbers, difference, color=color, linestyle=':')
        cumulative_ax.set_xlim(codon_numbers[0])
        cumulative_ax.set_ylim(-0.02, 1.02)
        
        cumulative_ax.legend(loc='upper right', framealpha=0.5)
        fig.suptitle('{0} - length {1} fragments\n{2}'.format(gene_name, fragment_length, exp_name))

    return codon_numbers, frame_counts_list, fraction_frames_so_far, fraction_frames_remaining

def plot_RPKMs():
    experiments = [
        ('geranshenko1', '/home/jah/projects/arlen/experiments/gerashchenko_pnas/Initial_rep1_foot/results/Initial_rep1_foot_rpf_positions.txt'),
        #('geranshenko2', '/home/jah/projects/arlen/experiments/gerashchenko_pnas/Initial_rep2_foot/results/Initial_rep2_foot_rpf_positions.txt'),
        ('ingolia1', '/home/jah/projects/arlen/experiments/ingolia_science/Footprints-rich-1/results/Footprints-rich-1_rpf_positions.txt'),
        ('ingolia2', '/home/jah/projects/arlen/experiments/ingolia_science/Footprints-rich-2/results/Footprints-rich-2_rpf_positions.txt'),
        ('ingolia1_mRNA', '/home/jah/projects/arlen/experiments/ingolia_science/mRNA-rich-1/results/mRNA-rich-1_rpf_positions.txt'),
        #('R98S', '/home/jah/projects/arlen/experiments/belgium_8_6_13/R98S_cDNA_sample/results/R98S_cDNA_sample_rpf_positions.txt'),
        #('suppressed', '/home/jah/projects/arlen/experiments/belgium_8_6_13/Suppressed_R98S_cDNA_sample/results/Suppressed_R98S_cDNA_sample_rpf_positions.txt'),
        #('WT',  '/home/jah/projects/arlen/experiments/belgium_8_6_13/WT_cDNA_sample/results/WT_cDNA_sample_rpf_positions.txt'),
    ]

    names = [name for name, _ in experiments]
    rpf_positions_lists = [Serialize.read_file(fn, 'rpf_positions') for _, fn in experiments]
    RPKMs_list = [get_TPMs(rpf_positions_list) for rpf_positions_list in rpf_positions_lists]
    vals = [[val for name, val in sorted(RPKMs.items())] for RPKMs in RPKMs_list]
    
    fig = plt.figure(figsize=(12, 12))
    for r in range(len(names)):
        for c in range(r + 1, len(names)):
            ax = fig.add_subplot(len(names) - 1, len(names) - 1, r * (len(names) - 1) + (c - 1) + 1)
            first = names[c]
            second = names[r]
            xs = vals[r]
            ys = vals[c]

            print sum(xs)
            print sum(ys)
            print
            
            ax.scatter(xs, ys, s=1)
            ax.set_yscale('log')
            ax.set_xscale('log')
            ax.set_xlim(1e-1, 5e4)
            ax.set_ylim(1e-1, 5e4)
            ax.plot([1e-2, 1e5], [1e-2, 1e5], '-', color='red', alpha=0.2)
            ax.set_xlabel(first)
            ax.set_ylabel(second)