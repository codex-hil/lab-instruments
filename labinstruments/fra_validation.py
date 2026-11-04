"""Quantitative commissioning comparison, separate from measurement or trust approval."""
import cmath
import math
from .fra_math import wrap_phase


def compare(result,kind='loopback',resistance_ohm=None,capacitance_f=None,gain_tolerance_db=.5,phase_tolerance_deg=5,cutoff_tolerance_percent=5):
    if kind not in ('loopback','rc'):raise ValueError('comparison must be loopback or rc')
    if kind=='rc':
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (resistance_ohm,capacitance_f)):raise ValueError('positive R and C required')
        fc=1/(2*math.pi*resistance_ohm*capacitance_f)
    else:fc=None
    for tolerance in (gain_tolerance_db,phase_tolerance_deg,cutoff_tolerance_percent):
        if not math.isfinite(tolerance) or tolerance<0:raise ValueError('invalid comparison tolerance')
    errors=[]
    for p in result['points']:
        if p['status']!='ok':continue
        h=1+0j if kind=='loopback' else 1/(1+1j*p['frequency_hz']/fc)
        expected_gain=20*math.log10(abs(h));expected_phase=math.degrees(cmath.phase(h))
        errors.append(dict(frequency_hz=p['frequency_hz'],expected_gain_db=expected_gain,expected_phase_deg=expected_phase,
                           gain_error_db=p['gain_db']-expected_gain,phase_error_deg=wrap_phase(p['phase_deg']-expected_phase)))
    max_gain=max((abs(e['gain_error_db']) for e in errors),default=None)
    max_phase=max((abs(e['phase_error_deg']) for e in errors),default=None)
    measured_fc=None
    for a,b in zip(result['points'],result['points'][1:]):
        level=-10*math.log10(2)
        if a['status']==b['status']=='ok' and a['gain_db']>=level>=b['gain_db'] and a['gain_db']!=b['gain_db']:
            fraction=(level-a['gain_db'])/(b['gain_db']-a['gain_db'])
            measured_fc=math.exp(math.log(a['frequency_hz'])+fraction*math.log(b['frequency_hz']/a['frequency_hz']));break
    good=bool(errors) and len(errors)==len(result['points']) and result['status']=='completed'
    passed=good and max_gain<=gain_tolerance_db and max_phase<=phase_tolerance_deg and (kind!='rc' or (measured_fc is not None and abs(100*(measured_fc/fc-1))<=cutoff_tolerance_percent))
    return dict(kind=kind,simulation=bool(result.get('simulation')),trust_state='UNTRUSTED',
        comparison_status='PASS' if passed else 'FAIL',note='Numerical comparison only; not a trust promotion or proof of physical fixture identity.',
        resistance_ohm=resistance_ohm,capacitance_f=capacitance_f,expected_cutoff_hz=fc,measured_cutoff_hz=measured_fc if kind=='rc' else None,
        cutoff_error_percent=100*(measured_fc/fc-1) if fc and measured_fc else None,
        gain_tolerance_db=gain_tolerance_db,phase_tolerance_deg=phase_tolerance_deg,cutoff_tolerance_percent=cutoff_tolerance_percent,
        max_abs_gain_error_db=max_gain,max_abs_phase_error_deg=max_phase,
        rms_gain_error_db=math.sqrt(sum(e['gain_error_db']**2 for e in errors)/len(errors)) if errors else None,
        rms_phase_error_deg=math.sqrt(sum(e['phase_error_deg']**2 for e in errors)/len(errors)) if errors else None,errors=errors)
