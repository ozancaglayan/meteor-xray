#!/usr/bin/env python

import os
import re
import sys
import shutil
import tempfile
import subprocess

from alignment import read_align_file, ALIGN_DEFAULT, ALIGN_METEOR, NO_MATCH


xelatex_cmd = '/usr/bin/xelatex'
gnuplot_cmd = '/usr/bin/gnuplot'
MAX_LEN = 50
GNUPLOT_HISTOGRAM = '''\
set auto x
set auto y
set style data histogram
set style histogram cluster gap 1
set style fill solid border -1
set boxwidth 0.9
set xtic rotate by -45 scale 0
set xlabel '{label}'
set ylabel 'Number of segments'
set terminal postscript eps enhanced color solid rounded 18
set output '{eps}'
plot '{data}' u 2:xtic(1) ti col{columns}
'''

DOC_HEADER_COMPARE = r'''

\noindent\large Meteor Alignments\\

\noindent\normalsize Reference top row\\
{sys1} (sentence 1) left column\\
{sys2} (sentence 2) right column\\\\
Matches identified by color (sen 1) and symbol (sen 2)\\\\
Color spectrum follows reference word order\\\\

\small
\noindent\begin{{tabular}}{{|l|c|c|}}
\hline
Match Type&Sentence 1&Sentence 2\\
\hline
Exact&\color{{z}}{{$\blacksquare$}}&\rex\\
\hline
Stem / Synonym / Paraphrase&\color{{y}}{{$\blacksquare$}}&\rap\\
\hline
\end{{tabular}}

\vspace{{6pt}}
\noindent Key: match markers for sentences
\newpage

'''

DOC_HEADER_SINGLE = r'''

\noindent\large Meteor Alignments for {sysname}\\

\noindent\normalsize Reference top row\\
Hypothesis left column\\
Matches identified by color and symbol\\\\
Color spectrum follows reference word order\\\\

\small
\noindent\begin{{tabular}}{{|l|p{{10pt}}|}}
\hline
Match Type&\\
\hline
Exact&\ssp\mex\\
\hline
Stem / Synonym / Paraphrase&\ssp\map\\
\hline
\end{{tabular}}

\vspace{{6pt}}
\noindent Key: match markers for sentences
\newpage

'''

DOC_HEADER_ALIGN = r'''

\noindent\large\textsc{Meteor} Alignments\\

\noindent\normalsize Reference top row\\
Hypothesis left column\\
Matches identified by color and symbol\\\\
Color spectrum follows reference word order\\\\

\small
\noindent\begin{tabular}{|l|p{10pt}|}
\hline
Match Type&\\
\hline
Exact&\ssp\mex\\
\hline
Stem / Synonym / Paraphrase&\ssp\map\\
\hline
Deleted&\ssp\mrm\\
\hline
\end{tabular}

\vspace{6pt}
\noindent Key: match markers for sentences
\newpage

'''

DOC_FOOTER = r'''\end{document}'''


DEC_HEADER1 = r'''\documentclass[landscape]{article}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%          Include these packages and declarations in your tex file            %
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

\usepackage{rotating}
\usepackage{colortbl}
\usepackage{amssymb}
\usepackage{amsmath}
\usepackage[T1]{fontenc}
'''

DEC_HEADER2 = r'''

\definecolor{z}{rgb}{0.7,0.7,0.7}
\definecolor{g}{rgb}{0.5,1.0,0.5}
\definecolor{y}{rgb}{1.0,1.0,0.5}
\definecolor{r}{rgb}{1.0,0.5,0.5}
\definecolor{gb}{rgb}{0.0,0.5,0.0}
\definecolor{rb}{rgb}{0.5,0.0,0.0}


\newcommand{\ssp}{\hspace{2pt}}
\newcommand{\lex}{\cellcolor{z}}
\newcommand{\lap}{\cellcolor{y}}
\newcommand{\rex}{$\bullet$}
\newcommand{\rap}{$\boldsymbol\circ$}
\newcommand{\mex}{\cellcolor{g}$\bullet$}
\newcommand{\map}{\cellcolor{y}$\boldsymbol\circ$}
\newcommand{\mrm}{\cellcolor{r}X}

% Search for '%Table start' and '%Table end' to find alignment boundaries

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

\usepackage[margin=0.5in]{geometry}
\pagenumbering{0}
%\renewcommand{\rmdefault}{phv} % Arial
%\renewcommand{\sfdefault}{phv} % Arial
\renewcommand{\tabcolsep}{1pt}

\begin{document}
'''

FILL = {'ex': r'\mex', 'ap': r'\map', 'rm': r'\mrm'}
FILL_L = {'ex': r'\lex', 'ap': r'\lap'}
FILL_R = {'ex': r'\rex', 'ap': r'\rap'}


def escape(s):
    s = s.replace('\\', '\\backslash')
    s = re.sub('([$&%{}#_])', r'\\\1', s)
    return s


def print_align_table(tex_out, a1, a2=None, a_type=ALIGN_METEOR):
    '''LaTeX generation function: use with caution'''

    print(r'%Table start', file=tex_out)
    # Print color declarations
    r = 0.6
    g = 0.6
    b = 1.0
    step = 0.4 / max(1, len(a1.sen2))
    half = len(a1.sen2) / 2
    for i in range(len(a1.sen2)):
        if i >= half:
            r += step * 1.5
            g += step * .25
            b -= step * 1.5
        else:
            r += step * .5
            g += step * 1.0
            b -= step * .5
        print(r'\definecolor{{ref{0}}}{{rgb}}{{{1},{2},{3}}}'.format(
            i, min(1.0, r), min(1.0, g), min(1.0, b)), file=tex_out)
    # Print table start
    line = r'\noindent\begin{tabular}{|l'
    for i in range(len(a1.sen2)):
        line += r'|'
        line += r'p{10pt}'
    if a2:
        line += r'|l'
    line += r'|}'
    print(line, file=tex_out)
    print(r'\hline', file=tex_out)
    # Print sentence 2
    line = ''
    if a2:
        line += r'\Large\color{z}{$\blacksquare$} \color{y}{$\blacksquare$}'
    for i in range(len(a1.sen2)):
        w2 = escape(a1.sen2[i])
        line += r'&\begin{sideways}' + r'\cellcolor{{ref{0}}}'.format(i) + \
                w2 + '\hspace{12pt}\end{sideways}'
    if a2:
        line += r'&\rex \rap'
    print(line + r'\\', file=tex_out)
    # Print each row for sentences a1.sen1, a2.sen1
    max_len = max(len(a1.sen1), len(a2.sen1)) if a2 else len(a1.sen1)
    fill1 = FILL
    if a2:
        fill1 = FILL_L
        fill2 = FILL_R
    for i in range(max_len):
        print(r'\hline', file=tex_out)
        line = ''
        if i < len(a1.sen1):
            line += r'\ssp '
            if a1.sen1_matched[i] != NO_MATCH:
                line += r'\cellcolor{{ref{0}}}'.format(a1.sen1_matched[i])
            line += escape(a1.sen1[i]) + r' \ssp'
        for j in range(len(a1.sen2)):
            line += r'&\hspace{2pt}'
            if i < len(a1.sen1):
                match = a1.matrix[i][j]
                if match:
                    line += fill1[a1.matrix[i][j]]
            if a2 and i < len(a2.sen1):
                match = a2.matrix[i][j]
                if match:
                    line += fill2[match]
        if a2:
            line += r'&'
            if i < len(a2.sen1):
                line += r'\ssp '
                if a2.sen1_matched[i] != NO_MATCH:
                    line += r'\cellcolor{{ref{0}}}'.format(a2.sen1_matched[i])
                line += escape(a2.sen1[i]) + r'\ssp '
        print(line + r'\\', file=tex_out)
    print(r'\hline', file=tex_out)
    # Print table footer
    print(r'\end{tabular}', file=tex_out)
    print(r'', file=tex_out)
    print(r'\vspace{6pt}', file=tex_out)
    # Print alignment information
    if a_type == ALIGN_DEFAULT:
        print(r'\noindent {0}'.format(a1.name), file=tex_out)
    # Compare stats
    elif a_type == ALIGN_METEOR:
        print(r'\noindent Segment {0}\\\\'.format(escape(a1.name)), file=tex_out)
        if a2:
            p_diff = a2.p - a1.p
            r_diff = a2.r - a1.r
            fr_diff = a2.frag - a1.frag
            sc_diff = a2.score - a1.score

            print(r'\noindent\begin{tabular}{lm{12pt}rm{24pt}rm{24pt}r}', file=tex_out)
            print(r'\hline', file=tex_out)
            print(r'P:&&{0:.3f}&\centering vs&{1:.3f}&\centering :&{{\bf\color{{{2}}}{{{3:.3f}}}}}\\'.format(a1.p, a2.p, 'gb' if p_diff >= 0 else 'rb', p_diff), file=tex_out)
            print(r'R:&&{0:.3f}&\centering vs&{1:.3f}&\centering :&{{\bf\color{{{2}}}{{{3:.3f}}}}}\\'.format(a1.r, a2.r, 'gb' if r_diff >= 0 else 'rb', r_diff), file=tex_out)
            print(r'Frag:&&{0:.3f}&\centering vs&{1:.3f}&\centering :&{{\bf\color{{{2}}}{{{3:.3f}}}}}\\'.format(a1.frag, a2.frag, 'rb' if fr_diff > 0 else 'gb', fr_diff), file=tex_out)
            print(r'Score:&&{0:.3f}&\centering vs&{1:.3f}&\centering :&{{\bf\color{{{2}}}{{{3:.3f}}}}}\\'.format(a1.score, a2.score, 'gb' if sc_diff >= 0 else 'rb', sc_diff), file=tex_out)
        else:
            print(r'\noindent\begin{tabular}{lm{12pt}r}', file=tex_out)
            print(r'\hline', file=tex_out)
            print(r'P:&&{0:.3f}\\'.format(a1.p), file=tex_out)
            print(r'R:&&{0:.3f}\\'.format(a1.r), file=tex_out)
            print(r'Frag:&&{0:.3f}\\'.format(a1.frag), file=tex_out)
            print(r'Score:&&{0:.3f}\\'.format(a1.score), file=tex_out)
        print(r'\end{tabular}', file=tex_out)
    # End table
    print(r'%Table end', file=tex_out)
    print('', file=tex_out)
    print(r'\newpage', file=tex_out)
    print('', file=tex_out)


def write_plot_hist(work_dir, dat_file, plot_file, eps_file, xlabel='Score', num_data_cols=1):
    uc_label = xlabel[0].upper() + xlabel[1:]
    col_line = ''
    for i in range(num_data_cols - 1):
        col_line += ', \'\' u {0} ti col'.format(i + 3)
    plot_out = open(shutil.os.path.join(work_dir, plot_file), 'w')
    print(GNUPLOT_HISTOGRAM.format(data=dat_file, eps=eps_file,
          label=uc_label, columns=col_line), file=plot_out)
    plot_out.close()


def gnuplot(work_dir, plot_file):
    subprocess.Popen([gnuplot_cmd, plot_file], cwd=work_dir,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE).wait()


def get_font(uni):
    if uni:
        return r'''\usepackage{fontspec}
\setmainfont{unifont}
'''
    else:
        return r'''\renewcommand{\rmdefault}{phv} % Arial
\renewcommand{\sfdefault}{phv} % Arial
'''


def check_xelatex():
    if not os.path.exists(xelatex_cmd):
        print('Could not find xelatex_cmd \'{0}\''.format(xelatex_cmd))
        print('Please install xetex or update path in Generation.py')
        return False
    return True


def check_gnuplot():
    if not os.path.exists(xelatex_cmd):
        print('Could not find gnuplot_cmd \'{0}\''.format(gnuplot_cmd))
        print('Please install gnuplot or update path in Generation.py')
        return False
    return True


def check_printable(a1, a2=None):
    # Too long
    if len(a1.sen2) > MAX_LEN:
        print('Skipping', a1.name, '- too large:',
              len(a1.sen2), 'reference words', file=sys.stderr)
        return False
    # Different references?
    if a2 and a1.sen2 != a2.sen2:
        print('Skipping', a1.name,
              '- different references used', file=sys.stderr)
        return False
    return True


def xelatex(tex_file, pdf_file, work_dir=shutil.os.curdir):
    # Working dir
    out_dir = tempfile.mkdtemp()
    # PDF output file
    if '.' in tex_file:
        out_pdf = tex_file[0:tex_file.rfind('.')] + '.pdf'
    else:
        out_pdf = tex_file + '.pdf'
    # Run xelatex
    subprocess.Popen([xelatex_cmd, '-interaction', 'batchmode',
                      '-output-directory', out_dir, tex_file], cwd=work_dir,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE).wait()
    # Copy pdf file and remove temp files
    shutil.copyfile(shutil.os.path.join(out_dir, out_pdf), pdf_file)
    shutil.rmtree(out_dir)


def main(argv):
    if not check_xelatex():
        sys.exit()

    if len(argv[1:]) < 2:
        print('usage: {0} <align.out> <prefix> [max]'.format(argv[0]))
        print('writes: <prefix>.pdf, <prefix>.tex')
        print('max determines max number of alignments to visualize')
        sys.exit()

    align_file = argv[1]
    prefix = argv[2]
    max_align = int(argv[3]) if len(argv[1:]) > 2 else -1

    pdf_file = prefix + '.pdf'
    tex_file = prefix + '.tex'

    alignments = read_align_file(align_file, max_align=max_align, a_type=ALIGN_DEFAULT)

    tex_out = open(tex_file, 'w')
    print(DEC_HEADER1, file=tex_out)
    print(get_font(True), file=tex_out)
    print(DEC_HEADER2, file=tex_out)
    print(DOC_HEADER_ALIGN, file=tex_out)
    for i in range(len(alignments)):
        a = alignments[i]
        if not check_printable(a):
            continue
        print_align_table(tex_out, a, a_type=ALIGN_DEFAULT)
    # Print footer
    print(DOC_FOOTER, file=tex_out)
    # Close file
    tex_out.close()
    print('Compiling {0} - this may take a few minutes...'.format(pdf_file), file=sys.stderr)
    xelatex(tex_file, pdf_file)


if __name__ == '__main__':
    main(sys.argv)
