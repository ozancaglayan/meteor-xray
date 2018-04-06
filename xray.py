#!/usr/bin/env python

import os
import sys
import shutil
import optparse
from functools import cmp_to_key

# from alignment import *
from visualization import check_gnuplot, check_printable, check_xelatex
from visualization import gnuplot, xelatex
from visualization import DOC_HEADER_COMPARE, DOC_HEADER_SINGLE
from visualization import DEC_HEADER1, DEC_HEADER2, DOC_FOOTER
from visualization import get_font, write_plot_hist, print_align_table
from alignment import cmp_score, cmp_score_best, cmp_score_diff, extract_scores
from alignment import read_align_file, get_score_dist


def write_dat_file(dat_file, data, xlabel='Score', syslabels=None):
    ROW_LABEL = ['0.0-0.1', '0.1-0.2', '0.2-0.3', '0.3-0.4',
                 '0.4-0.5', '0.5-0.6', '0.6-0.7', '0.7-0.8',
                 '0.8-0.9', '0.9-1.0']
    col_label = [xlabel[0].upper() + xlabel[1:]]
    for i in range(len(data)):
        if syslabels and len(syslabels) > i:
            col_label.append(syslabels[i])
        else:
            col_label.append('System-{0}'.format(i + 1))
    dat_out = open(dat_file, 'w')
    print('\t'.join(col_label), file=dat_out)
    for row in zip(ROW_LABEL, list(zip(*data))):
        print(row[0] + '\t' + '\t'.join([str(x) for x in row[1]]), file=dat_out)
    dat_out.close()


def main(argv):

    if not (check_xelatex() and check_gnuplot()):
        sys.exit(1)

    # Options
    opt = optparse.OptionParser(
      usage='Usage: %prog [options] <align.out> [align.out2 ...]')
    opt.add_option('-c', '--compare', action='store_true', dest='compare',
                   default=False,
                   help='compare alignments of two result sets (only first 2 input files used)')
    opt.add_option('-b', '--best-first', action='store_true', dest='bestfirst',
                   default=False,
                   help='Sort by improvement of sys2 over sys1')
    opt.add_option('-n', '--no-align', action='store_true', dest='noalign',
                   default=False,
                   help='do not visualize alignments')
    opt.add_option('-x', '--max', dest='maxalign', default='-1',
                   metavar='MAX',
                   help='max alignments to sample (default use all)')
    opt.add_option('-p', '--prefix', dest='prefix', default='mx',
                   metavar='PRE',
                   help='prefix for output files (default mx)')
    opt.add_option('-l', '--label', dest='label', default=None,
                   metavar='LBL',
                   help='optional system label list, comma separated: label1,label2,...')
    opt.add_option('-u', '--unifont', action='store_true', dest='uni',
                   default=False,
                   help='use unifont (use for non-western languages)')
    opt.add_option('-r', '--right-to-left', action='store_true', dest='rtl',
                   default=False,
                   help='language written right to left')

    # Parse
    o, a = opt.parse_args()
    if not a:
        print('MX: X-Ray your translation output')
        opt.print_help()
        sys.exit(1)
    compare = o.compare
    best_first = o.bestfirst
    no_align = o.noalign
    max_align = int(o.maxalign)
    prefix = o.prefix
    label = o.label
    uni = o.uni
    rtl = o.rtl
    align_files = a

    seg_scores = []

    label_list = label.split(',') if label else []
    for i in range(len(label_list)):
        label_list[i] = label_list[i][0].upper() + label_list[i][1:]
    for i in range(len(label_list), len(a)):
        label_list.append('System-{0}'.format(i + 1))

    pre_dir = prefix + '-files'
    try:
        os.mkdir(pre_dir)
    except Exception as e:
        print('Dir {0} exists, will overwrite contents'.format(pre_dir),
              file=sys.stderr)

    #
    # Visualize alignments
    #

    # Compare 2 alignments
    if compare:
        # File check
        if len(align_files) < 2:
            print('Comparison requires 2 alignment files')
            sys.exit(1)
        # Out files
        pdf_file = prefix + '-align.pdf'
        tex_file = 'align.tex'
        # Read alignments
        align_1 = read_align_file(a[0], max_align)
        align_2 = read_align_file(a[1], max_align)
        seg_scores.append(extract_scores(align_1))
        seg_scores.append(extract_scores(align_2))
        alignments = list(zip(align_1, align_2))
        alignments.sort(
            key=cmp_to_key(cmp_score_best if best_first else cmp_score_diff),
            reverse=True)
        if not no_align:
            # Write tex file
            tex_out = open(os.path.join(pre_dir, tex_file), 'w')
            # Header
            print(DEC_HEADER1, file=tex_out)
            print(get_font(uni), file=tex_out)
            print(DEC_HEADER2, file=tex_out)
            print(DOC_HEADER_COMPARE.format(sys1=label_list[0],
                  sys2=label_list[1]), file=tex_out)
            # Print each alignment
            for i in range(len(alignments)):
                a1, a2 = alignments[i]
                if rtl:
                    a1.rtl()
                    a2.rtl()
                if not check_printable(a1, a2):
                    continue
                print_align_table(tex_out, a1, a2)
            # Print footer
            print(DOC_FOOTER, file=tex_out)
            # Close file
            tex_out.close()
            # Compile pdf file
            print('Compiling {0} - this may take a few minutes...'.format(pdf_file), file=sys.stderr)
            xelatex(tex_file, pdf_file, work_dir=pre_dir)
    # Write N individual alignment files
    else:
        for i in range(len(align_files)):
            # Out files
            pdf_file = '{0}-align-{1}.pdf'.format(prefix, label_list[i].lower())
            tex_file = 'align-{1}.tex'.format(prefix, i + 1)
            # Read alignments
            alignments = read_align_file(a[i], max_align)
            seg_scores.append(extract_scores(alignments))
            alignments.sort(key=cmp_to_key(cmp_score), reverse=True)
            if no_align:
                continue
            # Write tex file
            tex_out = open(os.path.join(pre_dir, tex_file), 'w')
            # Header
            print(DEC_HEADER1, file=tex_out)
            print(get_font(uni), file=tex_out)
            print(DEC_HEADER2, file=tex_out)
            print(DOC_HEADER_SINGLE.format(sysname=label_list[i]), file=tex_out)
            # Print each alignment
            for i in range(len(alignments)):
                a1 = alignments[i]
                if rtl:
                    a1.rtl()
                if not check_printable(a1):
                    continue
                print_align_table(tex_out, a1)
            # Print footer
            print(DOC_FOOTER, file=tex_out)
            # Close file
            tex_out.close()
            # Compile pdf file
            print('Compiling {0} - this may take a few minutes...'.format(pdf_file), file=sys.stderr)
            xelatex(tex_file, pdf_file, work_dir=pre_dir)

    #
    # Graph scores
    #

    # All scores
    for stat in ('score', 'frag', 'p', 'r'):
        dat_file = '{0}-all.dat'.format(stat)
        plot_file = '{0}-all.plot'.format(stat)
        eps_file = '{0}-all.eps'.format(stat)
        dists = []
        for scores in seg_scores:
            dists.append(get_score_dist([eval('x.' + stat) for x in scores]))
        write_dat_file(os.path.join(pre_dir, dat_file), dists, stat,
                       label_list)
        write_plot_hist(pre_dir, dat_file, plot_file, eps_file, stat, len(dists))
        gnuplot(pre_dir, plot_file)

    # Scores by length
    for stat in ('score', 'frag', 'p', 'r'):
        for r in [[1, 10], [11, 25], [26, 50], [51]]:
            if len(r) == 2:
                label = '{0}-{1}'.format(r[0], r[1])
            else:
                label = '{0}+'.format(r[0])
            dat_file = '{0}-{1}.dat'.format(stat, label)
            plot_file = '{0}-{1}.plot'.format(stat, label)
            eps_file = '{0}-{1}.eps'.format(stat, label)
            dists = []
            for scores in seg_scores:
                if len(r) == 2:
                    values = [eval('x.' + stat) for x in scores if x.sen_len >= r[0] and x.sen_len <= r[1]]
                else:
                    values = [eval('x.' + stat) for x in scores if x.sen_len >= r[0]]
                dists.append(get_score_dist(values))
            write_dat_file(os.path.join(pre_dir, dat_file), dists,
                           stat, label_list)
            write_plot_hist(pre_dir, dat_file, plot_file, eps_file, stat, len(dists))
            gnuplot(pre_dir, plot_file)

    # Write files
    score_pdf = prefix + '-score.pdf'
    score_tex = 'score.tex'
    shutil.copyfile(os.path.join(os.path.dirname(__file__),
                    'score_template.tex'), os.path.join(pre_dir, score_tex))
    print('Compiling {0}...'.format(score_pdf), file=sys.stderr)
    xelatex(score_tex, score_pdf, work_dir=pre_dir)
    print('Supporting files written to {0}.'.format(pre_dir), file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv)
