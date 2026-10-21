"""Render reviewed layout from frozen position-hold selection verdicts."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import run_position_hold_selection as experiment
import run_reasoning_comparison as r


def main():
    run=experiment.RUN
    result=json.loads((run/'RESULT.json').read_text())
    assert result['status']=='PENDING_VISUAL_REVIEW'
    experiment.load_cases()
    summaries=result['summaries']
    fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
    for ax,encoding in zip(axes,experiment.ENCODINGS):
        for i,arm in enumerate(experiment.ARMS):
            values=[next(x['violation_rate']*100 for x in summaries
                         if x['encoding']==encoding and x['arm']==arm and x['hold_ms']==hold)
                    for hold in (500,2000)]
            ax.bar([j+(i-1)*.23 for j in range(2)],values,width=.22,label=arm.upper())
        ax.set_xticks([0,1],['0.5 s hold','2.0 s hold'])
        ax.set(title='Provided maxima' if encoding=='interval_maxima' else 'XY waypoint lists',
               ylabel='Violating selections (%)',ylim=(0,105))
        ax.grid(axis='y',alpha=.2)
        ax.legend()
    fig.suptitle('Position-hold candidate selection: 0.200 m radius\n'
                 'Existing temporal adapters; synthetic task transfer; three training seeds',fontsize=11)
    for suffix in ('pdf','png'):
        fig.savefig(run/f'position_hold_selection.{suffix}',dpi=170,bbox_inches='tight')
    plt.close(fig)
    result['reviewed_renderer']=dict(source=str(Path(__file__).resolve()),sha256=r.digest(Path(__file__)))
    r.write_json(run/'RESULT.json',result)
    print('Reviewed plot layout saved; numeric verdicts unchanged.')


if __name__=='__main__':
    main()
