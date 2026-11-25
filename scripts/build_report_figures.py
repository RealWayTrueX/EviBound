#!/usr/bin/env python3
"""Draw the report's result figures from the committed records.

  fig_formal_test    v2: unsafe effects under attack, and clean completions split by whether
                     a device rule was broken (one column wide)
  fig_effects        v2 and v3: paired contrasts with 95% intervals and decisions (one column)
  fig_ladder_results v3.1: where episodes ended under each refusal message, over all
                     episodes and within three kinds of recovery turn (full width)
  fig_claims         v3.1: the thirteen confirmatory contrasts behind claims C1 to C6 (one column)

Every plotted value is read from the same artifacts as ``build_report_numbers.py``; nothing
is typed in. Figures are drawn at their printed size (88.9 mm or 182 mm wide), so the type
in the PDF is the type on the page. Colours and their meaning are in ``report_style.py``.

Usage::

    python3 scripts/build_report_figures.py            # write report/figures/fig_*.pdf (+ .png)
    python3 scripts/build_report_figures.py --data     # print the plotted values as JSON
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import build_report_numbers as report  # noqa: E402
import report_style as S  # noqa: E402

OUT = ROOT / 'report' / 'figures'
MINUS = '−'

# The ladder in the order of the report: condition, level, label in figures, group.
LADDER = (
    ('M', 'L0', 'verdict', 'describe'),
    ('M_recover', 'L1', 'reason', 'describe'),
    ('M_reading', 'L1r', 'reason + reading', 'describe'),
    ('M_full', 'L2a', 'list', 'list'),
    ('M_menu2', 'L2a′', 'list, reworded', 'list'),
    ('M_plan', 'L2b', 'plan review', 'plan'),
    ('M_seq', 'L3', 'sequence', 'plan'),
)
REFERENCES = (('B2_plan', 'no evidence binding'), ('B0', 'no guard'))
KINDS = (('interrupted', 'interrupted'), ('revise', 'revise'), ('reselect', 'reselect'))


# ------------------------------------------------------------------ data

def signed(points):
    points = round(points, 1)
    if points == 0:
        return '0.0'
    return ('+' if points > 0 else MINUS) + f'{abs(points):.1f}'


def interval(effect):
    """Estimate and interval of one contrast in percentage points."""
    estimate, low, high = (100 * value for value in effect)
    return {'estimate': estimate, 'low': low, 'high': high,
            'text': f'{signed(estimate)} [{signed(low)}, {signed(high)}]'}


def data_formal_test():
    values = report.build_numbers().values
    rows = []
    for condition, key, label in (('B0', 'b0', 'no guard'), ('B1', 'b1', 'prompt reminder'),
                                  ('B2', 'b2', 'rules, cited reading'),
                                  ('M_no_freshness', 'nofresh', 'no age check'),
                                  ('Always_refresh', 'refresh', 'always re-read'), ('M', 'm', 'EviBound')):
        rows.append({'condition': condition, 'label': label,
                     'unsafe': int(values[f'v2.att.{key}.unsafe']),
                     'goal': int(values[f'v2.clean.{key}.goal']), 'safe': int(values[f'v2.clean.{key}.safe'])})
    return {'cell': int(values['v2.cell']), 'rows': rows}


EFFECT_ROWS = (
    # key, study, label, rule, standing
    ('v2.safety', 'v2', 'Safety: unsafe effects, B2 − M', 'superiority', 'primary'),
    ('v2.utility', 'v2', 'Utility: goal reached, M − B0', 'non_inferiority', 'primary'),
    ('v2.fresh', 'v2', 'Ablation: unsafe, no age check − M', 'superiority', 'secondary'),
    ('v3.S1', 'v3', 'S1 safety: unsafe effects, B2 − M', 'superiority', 'primary'),
    ('v3.U1', 'v3', 'U1 utility: goal reached, M − B0', 'non_inferiority', 'primary'),
    ('v3.U2', 'v3', 'U2 amended: rule-compliant goal', 'non_inferiority', 'amended'),
    ('v3.Udec', 'v3', 'U-dec post hoc: legitimate request', 'non_inferiority', 'posthoc'),
    ('v3.R1', 'v3', 'R1 aids: goal, with − without aids', 'superiority', 'secondary'),
)


def data_effects():
    effects = report.source_effects()
    values = report.build_numbers().values
    decisions = {key: decision for key, _, _, _, _, decision in report.EFFECT_ROWS}
    counts = {key: pair for key, _, _, pair, _, _ in report.EFFECT_ROWS}
    rows = []
    for key, study, label, rule, standing in EFFECT_ROWS:
        row = interval(effects[key])
        row.update({'key': key, 'study': study, 'label': label, 'rule': rule, 'standing': standing,
                    'decision': decisions[key],
                    'counts': f"{values[counts[key][0]]} vs {values[counts[key][1]]}"})
        rows.append(row)
    margin = 100 * float(report.load('week8_main_results.json')['primary_results']['utility']['non_inferiority_margin'])
    return {'rows': rows, 'margin': margin,
            'titles': {'v2': f"Formal test (v2): {values['v2.cell']} paired episodes, {values['v2.clusters']} structures",
                       'v3': f"Holdout (v3): {values['v3.cell']} paired episodes, {values['v3.clusters']} structures"}}


def data_ladder():
    record = report.v31_record()
    totals = report.v31_totals(record)
    kinds = record['kinds']['rows']
    rows = []
    for condition, level, label, group in LADDER:
        total = totals[condition]
        row = {'condition': condition, 'label': f'{level}  {label}', 'group': group, 'n': total['episodes'],
               'exact': total['exact_target'], 'unrequested': total['unrequested_change'], 'kinds': {}}
        for kind, _ in KINDS:
            cell = kinds[kind]['by_condition'][condition]
            row['kinds'][kind] = {'exact': cell['exact_target'], 'n': cell['n']}
        rows.append(row)
    for condition, label in REFERENCES:
        total = totals[condition]
        rows.append({'condition': condition, 'label': label, 'group': 'reference', 'n': total['episodes'],
                     'exact': total['exact_target'], 'unrequested': total['unrequested_change'], 'kinds': {}})
    return {'rows': rows, 'kind_n': {kind: kinds[kind]['n'] for kind, _ in KINDS}}


CLAIMS = (
    # claim, heading, rows of (contrast id, label)
    ('C1', 'the list causes unrequested changes', (('U1', 'list − reason'), ('W1', 'reworded list − reason'))),
    ('C2', 'the list stops interrupted plans', (('I1', 'reason − list'), ('I2', 'reason − reworded list'))),
    ('C3', 'advice on the plan repairs fewer plans', (('P1', 'reason − plan review'), ('P2', 'reason − sequence'))),
    ('C4', 'the trusted reading helps', (('R1', 'reason + reading − reason'),)),
    ('C5', 'the reason alone is not behind by 5 points',
     (('N1', 'reason − list'), ('N2', 'reason − reworded list'), ('N3', 'reason − plan review'),
      ('N4', 'reason − sequence'))),
    ('C6', 'evidence binding under attack', (('S1', 'unsafe effects, B2 − M'), ('S2', 'home unchanged, M − B2'))),
)


def data_claims():
    record = report.v31_record()
    groups = []
    for claim, heading, contrasts in CLAIMS:
        rows = []
        for contrast, label in contrasts:
            item = record['decisions'][contrast]
            effect = item['effect']
            row = interval((effect['estimate'], effect['ci95_low'], effect['ci95_high']))
            row.update({'id': contrast, 'label': label, 'rule': item['rule'],
                        'decision': {'unsupported': 'not supported'}.get(item['decision'], item['decision'])})
            rows.append(row)
        groups.append({'claim': claim, 'heading': heading, 'outcome': record['joint'][claim].replace('_', ' '),
                       'rows': rows})
    assert sum(len(group['rows']) for group in groups) == len(report.V31_CONFIRMATORY)
    return {'groups': groups, 'margin': -5.0}


DATA = {'fig_formal_test': data_formal_test, 'fig_effects': data_effects, 'fig_ladder_results': data_ladder,
        'fig_claims': data_claims}


# ------------------------------------------------------------------ drawing

def setup():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        'font.family': 'sans-serif', 'font.sans-serif': S.FONT_FAMILY, 'font.size': 7,
        'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
        'axes.edgecolor': S.AXIS, 'axes.linewidth': 0.6, 'axes.labelcolor': S.INK_2, 'axes.labelsize': 6.8,
        'axes.titlesize': 7.4, 'axes.titleweight': 'bold', 'axes.titlecolor': S.INK,
        'xtick.color': S.INK_2, 'ytick.color': S.INK, 'xtick.labelsize': 6.5, 'ytick.labelsize': 7,
        'xtick.major.width': 0.6, 'xtick.major.size': 2.2, 'ytick.major.size': 0,
        'grid.color': S.GRID, 'grid.linewidth': 0.6, 'legend.fontsize': 6.6, 'legend.frameon': False,
        'figure.dpi': 200, 'savefig.dpi': 400, 'hatch.linewidth': 0.5, 'text.color': S.INK,
    })
    return plt


def mm(value):
    return value / S.MM_PER_INCH


def clean_axis(ax, grid=True):
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    if grid:
        ax.xaxis.grid(True)
    ax.set_axisbelow(True)


def draw_formal_test(plt, data):
    rows, cell = data['rows'], data['cell']
    fig = plt.figure(figsize=(mm(S.COLUMN_MM), mm(39.5)))
    left = fig.add_axes([0.285, 0.315, 0.28, 0.555])
    right = fig.add_axes([0.655, 0.315, 0.28, 0.555])
    ys = list(range(len(rows)))[::-1]
    height = 0.56
    for ax in (left, right):
        clean_axis(ax)
        ax.set_xlim(0, cell)
        ax.set_xticks([0, 24, 48, 72])
        ax.set_ylim(-0.6, len(rows) - 0.4)
        ax.axvline(0, color=S.AXIS, linewidth=0.8)
    for y, row in zip(ys, rows):
        left.barh(y, row['unsafe'], height=height, color=S.RED, edgecolor='none')
        left.text(row['unsafe'] + 2, y, str(row['unsafe']), va='center', ha='left', fontsize=6.6)
        right.barh(y, row['safe'], height=height, color=S.BLUE, edgecolor='none')
        extra = row['goal'] - row['safe']
        if extra:
            right.barh(y, extra - 0.9, left=row['safe'] + 0.9, height=height - 0.07, color=S.RED_TINT,
                       edgecolor=S.RED, linewidth=0.7)
        right.text(row['goal'] + (2.9 if extra else 2), y, f"{row['safe']}+{extra}" if extra else str(row['goal']),
                   va='center', ha='left', fontsize=6.6)
    left.set_yticks(ys)
    left.set_yticklabels([row['label'] for row in rows])
    for tick, row in zip(left.get_yticklabels(), rows):
        if row['condition'] == 'M':
            tick.set_fontweight('bold')
    right.set_yticks([])
    left.set_title('Attacked: unsafe effect', loc='left', pad=4)
    right.set_title('Clean: goal reached', loc='left', pad=4)
    left.set_xlabel(f'episodes of {cell}', labelpad=1.5)
    right.set_xlabel(f'episodes of {cell}', labelpad=1.5)
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(facecolor=S.RED, label='unsafe effect'), Patch(facecolor=S.BLUE, label='no violation'),
                        Patch(facecolor=S.RED_TINT, edgecolor=S.RED, linewidth=0.7,
                              label='reached by breaking a rule')],
               loc='lower center', ncol=3, bbox_to_anchor=(0.5, -0.03), handlelength=1.3, handleheight=0.8,
               columnspacing=1.1, handletextpad=0.5)
    return fig


DECISION_COLOUR = {'supported': S.BLUE, 'not supported': S.RED}


def forest_row(ax, y, row, margin, x_text, filled):
    colour = DECISION_COLOUR.get(row['decision'], S.GREY)
    ax.plot([row['low'], row['high']], [y, y], color=colour, linewidth=1.3, solid_capstyle='butt', zorder=3)
    for end in (row['low'], row['high']):
        ax.plot([end, end], [y - 0.2, y + 0.2], color=colour, linewidth=1.0, zorder=3)
    ax.plot(row['estimate'], y, 'o', markersize=4.2, markerfacecolor=colour if filled else S.SURFACE,
            markeredgecolor=colour, markeredgewidth=1.0, zorder=4)
    if row['rule'] == 'non_inferiority':
        # the threshold of this row: the non-inferiority margin instead of zero
        ax.plot([margin, margin], [y - 0.36, y + 0.36], color=S.INK, linewidth=0.9, zorder=2)
    ax.text(x_text, y, row['text'], va='center', ha='left', fontsize=6.4, clip_on=False)


def forest_axis(ax, x_range, ticks, lines):
    """Axis of a forest plot. Grid and zero line are drawn behind the blocks of rows only,
    so that the headings between the blocks stand on a clear surface."""
    n_rows = len(lines)
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.set_xlim(*x_range)
    ax.set_ylim(-0.7, n_rows - 0.3)
    ax.set_xticks(ticks)
    ax.set_xticklabels([('+' if t > 0 else MINUS if t < 0 else '') + str(abs(t)) for t in ticks])
    ax.set_yticks([])
    ax.set_xlabel('paired difference, percentage points', labelpad=1.5)
    blocks, start = [], None
    for index, (kind, _) in enumerate(lines + [('title', None)]):
        if kind == 'row' and start is None:
            start = index
        elif kind != 'row' and start is not None:
            blocks.append((n_rows - index - 0.5, n_rows - 1 - start + 0.5))
            start = None
    for low, high in blocks:
        for tick in ticks:
            ax.plot([tick, tick], [low, high], color=S.INK_2 if tick == 0 else S.GRID,
                    linewidth=0.8 if tick == 0 else 0.6, zorder=1, solid_capstyle='butt')


def draw_effects(plt, data):
    rows = data['rows']
    lines = []                    # ('title', text) or ('row', row)
    previous = None
    for row in rows:
        if row['study'] != previous:
            lines.append(('title', data['titles'][row['study']]))
            previous = row['study']
        lines.append(('row', row))
    n = len(lines)
    fig = plt.figure(figsize=(mm(S.COLUMN_MM), mm(3.75 * n + 16)))
    ax = fig.add_axes([0.44, 0.285, 0.285, 0.70])
    x_range = (-30, 65)
    forest_axis(ax, x_range, [-20, 0, 20, 40, 60], lines)
    span = x_range[1] - x_range[0]
    x_label = x_range[0] - span * (0.44 / 0.285) + span * 0.012
    x_text = x_range[1] + span * 0.04
    for index, (kind, item) in enumerate(lines):
        y = n - 1 - index
        if kind == 'title':
            ax.text(x_label, y - 0.12, item, va='center', ha='left', fontsize=6.8, fontweight='bold', clip_on=False)
            continue
        ax.text(x_label + span * 0.03, y, item['label'], va='center', ha='left', fontsize=6.6, clip_on=False)
        forest_row(ax, y, item, data['margin'], x_text, filled=item['standing'] == 'primary')
    draw_key(fig, [('o', S.BLUE, True, 'supported'), ('o', S.RED, True, 'not supported'),
                   ('o', S.GREY, True, 'inconclusive or descriptive')], 0.02, 0.085)
    draw_key(fig, [('o', S.INK_2, False, 'secondary, amended or post hoc'),
                   ('|', S.INK, True, 'non-inferiority margin (' + MINUS + '5)')], 0.02, 0.028)
    return fig


def draw_key(fig, handles, x, y, step=None):
    """A one-line key in figure coordinates: marker, then its label in ink."""
    from matplotlib.lines import Line2D
    ax = fig.add_axes([0, 0, 1, 1], frameon=False)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    renderer = fig.canvas.get_renderer()
    width = fig.get_size_inches()[0] * fig.dpi
    for marker, colour, filled, label in handles:
        if marker == '|':
            ax.add_line(Line2D([x + 0.006, x + 0.006], [y - 0.016, y + 0.016], color=colour, linewidth=0.9))
        else:
            ax.plot(x + 0.006, y, marker, markersize=4.0, markerfacecolor=colour if filled else S.SURFACE,
                    markeredgecolor=colour, markeredgewidth=1.0)
        text = ax.text(x + 0.022, y, label, va='center', ha='left', fontsize=6.3, color=S.INK_2)
        x += 0.022 + text.get_window_extent(renderer).width / width + 0.02


def draw_claims(plt, data):
    lines = []
    for group in data['groups']:
        lines.append(('title', group))
        lines.extend(('row', row) for row in group['rows'])
    n = len(lines)
    fig = plt.figure(figsize=(mm(S.COLUMN_MM), mm(3.3 * n + 13)))
    ax = fig.add_axes([0.40, 0.158, 0.32, 0.838])
    x_range = (-15, 60)
    forest_axis(ax, x_range, [0, 20, 40, 60], lines)
    span = x_range[1] - x_range[0]
    x_label = x_range[0] - span * (0.40 / 0.32) + span * 0.012
    x_text = x_range[1] + span * 0.035
    renderer = fig.canvas.get_renderer()
    for index, (kind, item) in enumerate(lines):
        y = n - 1 - index
        if kind == 'title':
            heading = ax.text(x_label, y - 0.12, f"{item['claim']}  {item['heading']}: ", va='center', ha='left',
                              fontsize=6.7, fontweight='bold', clip_on=False)
            # the outcome follows the heading in the same line
            x_after = ax.transData.inverted().transform((heading.get_window_extent(renderer).x1, 0))[0]
            ax.text(x_after, y - 0.12, item['outcome'], va='center', ha='left', fontsize=6.7, fontweight='bold',
                    fontstyle='italic', clip_on=False)
            continue
        ax.text(x_label + span * 0.03, y, f"{item['id']}  {item['label']}", va='center', ha='left', fontsize=6.5,
                clip_on=False)
        forest_row(ax, y, item, data['margin'], x_text, filled=True)
    draw_key(fig, [('o', S.BLUE, True, 'part supported'), ('o', S.RED, True, 'part not supported'),
                   ('|', S.INK, True, 'non-inferiority margin (' + MINUS + '5)')], 0.02, 0.022)
    return fig


def draw_ladder(plt, data):
    rows = data['rows']
    n = len(rows)
    ladder_n = len(LADDER)
    # y positions: the seven messages, a gap, the two reference conditions
    ys = [n - index + (0.55 if index < ladder_n else 0) for index in range(n)]
    fig = plt.figure(figsize=(mm(S.PAGE_MM), mm(57)))
    panel_y, panel_h = 0.235, 0.575
    title_y = panel_y + panel_h + 0.105
    panels = {'exact': fig.add_axes([0.150, panel_y, 0.195, panel_h]),
              'unrequested': fig.add_axes([0.386, panel_y, 0.158, panel_h])}
    x0, width, gap = 0.594, 0.118, 0.017
    kind_axes = [fig.add_axes([x0 + index * (width + gap), panel_y, width, panel_h]) for index in range(len(KINDS))]
    height = 0.6

    def bars(ax, values, limit, ticks, labels, pad):
        clean_axis(ax)
        ax.set_xlim(0, limit)
        ax.set_xticks(ticks)
        ax.set_ylim(min(ys) - 0.65, max(ys) + 0.6)
        ax.set_yticks([])
        ax.axvline(0, color=S.AXIS, linewidth=0.8)
        for y, row, value, label in zip(ys, rows, values, labels):
            if value is None:
                continue
            ax.barh(y, value, height=height, color=S.GROUP_COLOUR[row['group']], edgecolor='none')
            ax.text(value + pad, y, label, va='center', ha='left', fontsize=6.4)

    exact = [100 * row['exact'] / row['n'] for row in rows]
    unrequested = [100 * row['unrequested'] / row['n'] for row in rows]
    bars(panels['exact'], exact, 100, [0, 25, 50, 75, 100], [f'{value:.1f}' for value in exact], 1.5)
    bars(panels['unrequested'], unrequested, 32, [0, 10, 20, 30], [f'{value:.1f}' for value in unrequested], 0.5)
    panels['exact'].set_yticks(ys)
    panels['exact'].set_yticklabels([row['label'] for row in rows])
    panels['exact'].tick_params(axis='y', pad=3)
    for key, title in (('exact', '(a) At the attainable target'), ('unrequested', '(b) Unrequested change')):
        fig.text(panels[key].get_position().x0, title_y, title, fontsize=7.4, fontweight='bold', va='bottom', ha='left')
        panels[key].set_xlabel(f"% of {rows[0]['n']:,} episodes", labelpad=1.5)
    for ax, (kind, name) in zip(kind_axes, KINDS):
        values, labels = [], []
        for row in rows:
            cell = row['kinds'].get(kind)
            values.append(None if not cell else 100 * cell['exact'] / cell['n'])
            labels.append('' if not cell else str(cell['exact']) + ('' if cell['n'] == data['kind_n'][kind] else f"/{cell['n']}"))
        bars(ax, values, 124, [0, 50, 100], labels, 2)
        ax.set_title(name, loc='left', pad=3.5, fontweight='normal', fontstyle='italic', fontsize=7.0)
        ax.set_xlabel(f"% of {data['kind_n'][kind]:,} turns", labelpad=1.5)
    fig.text(x0, title_y, '(c) At the attainable target, by kind of recovery turn',
             fontsize=7.4, fontweight='bold', va='bottom', ha='left')
    # key for the three groups of messages
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(facecolor=S.BLUE, label='describes'), Patch(facecolor=S.ORANGE, label='lists the legal writes'),
                        Patch(facecolor=S.AQUA, label='built from the rejected plan'),
                        Patch(facecolor=S.GREY, label='reference condition, not a message')],
               loc='lower left', ncol=4, bbox_to_anchor=(0.143, -0.035), handlelength=1.3, handleheight=0.8,
               columnspacing=1.8, handletextpad=0.5)
    return fig


DRAW = {'fig_formal_test': draw_formal_test, 'fig_effects': draw_effects, 'fig_ladder_results': draw_ladder,
        'fig_claims': draw_claims}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--data', action='store_true', help='print the plotted values as JSON and draw nothing')
    args = parser.parse_args(argv)
    data = {name: build() for name, build in DATA.items()}
    if args.data:
        print(json.dumps(data, indent=1, sort_keys=True))
        return 0
    plt = setup()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, draw in DRAW.items():
        fig = draw(plt, data[name])
        fig.savefig(OUT / f'{name}.pdf', metadata={'CreationDate': None, 'ModDate': None})
        fig.savefig(OUT / f'{name}.png')
        plt.close(fig)
        print(f'report/figures/{name}.pdf (+ png)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
