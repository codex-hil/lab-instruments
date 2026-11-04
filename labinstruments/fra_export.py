"""JSON is authoritative. Dependency-free CSV, SVG and PNG render the same points."""
import csv
import html
import io
import json
import math
import struct
import zlib
from pathlib import Path
from .fra_math import unwrap_phase

FIELDS=['frequency_hz','gain_db','phase_deg','phase_unwrapped_deg','vin_rms','vout_rms','gain_std_db','phase_std_deg','sample_rate_hz','record_length','averages','status']


def rows(result):
    ps=result['points']; phases=unwrap_phase([p['phase_deg'] if p['status']=='ok' else None for p in ps])
    return [dict(p,phase_unwrapped_deg=phase) for p,phase in zip(ps,phases)]


def csv_bytes(result):
    stream=io.StringIO(); w=csv.DictWriter(stream,fieldnames=FIELDS,extrasaction='ignore'); w.writeheader(); w.writerows(rows(result))
    return stream.getvalue().encode()


def drawing(result):
    """Common scene for SVG/PNG; gaps remain gaps, never join across bad points."""
    ps=rows(result); commands=[]
    def text(x,y,s): commands.append(('text',x,y,str(s)))
    def line(x1,y1,x2,y2,color): commands.append(('line',x1,y1,x2,y2,color))
    title='FRA '+('SIMULATION' if result.get('simulation') else result.get('trust_state','UNTRUSTED'))+' '+result.get('status','')
    text(20,25,title)
    start=result['config']['start_frequency']; stop=result['config']['stop_frequency']
    if start==stop: start/=1.2; stop*=1.2
    lo,hi=math.log10(start),math.log10(stop)
    def x(f): return 85+(math.log10(f)-lo)/(hi-lo)*860
    for top,field,label,color in [(60,'gain_db','GAIN [dB]','#126ac1'),(320,'phase_unwrapped_deg','PHASE [deg]','#b34c08')]:
        vals=[p[field] for p in ps if p['status']=='ok' and p[field] is not None]
        low=min(vals,default=-1); high=max(vals,default=1); pad=max((high-low)*.1,1); low-=pad;high+=pad
        y=lambda v: top+200-(v-low)/(high-low)*200
        text(85,top-10,label)
        for i in range(5):
            value=low+(high-low)*i/4; yy=y(value)
            line(85,yy,945,yy,'#dddddd'); text(10,yy+4,f'{value:.3g}')
        for i in range(6):
            xx=85+860*i/5; freq=10**(lo+(hi-lo)*i/5)
            line(xx,top,xx,top+200,'#dddddd'); text(xx-15,top+222,f'{freq:.3g}')
        last=None
        for p in ps:
            if p['status']!='ok' or p[field] is None: last=None;continue
            xy=(x(p['frequency_hz']),y(p[field]))
            if last: line(*last,*xy,color)
            line(xy[0]-2,xy[1],xy[0]+2,xy[1],color);line(xy[0],xy[1]-2,xy[0],xy[1]+2,color);last=xy
    text(380,575,'FREQUENCY [Hz] - LOG AXIS')
    text(20,600,'Invalid points omitted; phase unwrapped only for display.')
    return commands


def svg_bytes(result):
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="620" viewBox="0 0 1000 620"><rect width="1000" height="620" fill="white"/>']
    for item in drawing(result):
        if item[0]=='text':
            _,x,y,s=item;out.append(f'<text x="{x}" y="{y}" font-family="monospace" font-size="13">{html.escape(s)}</text>')
        else:
            _,x,y,xx,yy,col=item;out.append(f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{col}" stroke-width="2"/>')
    return (''.join(out)+'</svg>').encode()


# Small original 5x7 bitmap alphabet for a portable labeled PNG (no font/package dependency).
FONT={
'A':'01110 10001 10001 11111 10001 10001 10001','B':'11110 10001 10001 11110 10001 10001 11110',
'C':'01111 10000 10000 10000 10000 10000 01111','D':'11110 10001 10001 10001 10001 10001 11110',
'E':'11111 10000 10000 11110 10000 10000 11111','F':'11111 10000 10000 11110 10000 10000 10000',
'G':'01111 10000 10000 10111 10001 10001 01111','H':'10001 10001 10001 11111 10001 10001 10001',
'I':'11111 00100 00100 00100 00100 00100 11111','J':'00111 00010 00010 00010 10010 10010 01100',
'K':'10001 10010 10100 11000 10100 10010 10001','L':'10000 10000 10000 10000 10000 10000 11111',
'M':'10001 11011 10101 10101 10001 10001 10001','N':'10001 11001 10101 10011 10001 10001 10001',
'O':'01110 10001 10001 10001 10001 10001 01110','P':'11110 10001 10001 11110 10000 10000 10000',
'Q':'01110 10001 10001 10001 10101 10010 01101','R':'11110 10001 10001 11110 10100 10010 10001',
'S':'01111 10000 10000 01110 00001 00001 11110','T':'11111 00100 00100 00100 00100 00100 00100',
'U':'10001 10001 10001 10001 10001 10001 01110','V':'10001 10001 10001 10001 10001 01010 00100',
'W':'10001 10001 10001 10101 10101 10101 01010','X':'10001 10001 01010 00100 01010 10001 10001',
'Y':'10001 10001 01010 00100 00100 00100 00100','Z':'11111 00001 00010 00100 01000 10000 11111',
'0':'01110 10001 10011 10101 11001 10001 01110','1':'00100 01100 00100 00100 00100 00100 01110',
'2':'01110 10001 00001 00010 00100 01000 11111','3':'11110 00001 00001 01110 00001 00001 11110',
'4':'00010 00110 01010 10010 11111 00010 00010','5':'11111 10000 10000 11110 00001 00001 11110',
'6':'01110 10000 10000 11110 10001 10001 01110','7':'11111 00001 00010 00100 01000 01000 01000',
'8':'01110 10001 10001 01110 10001 10001 01110','9':'01110 10001 10001 01111 00001 00001 01110',
'-':'00000 00000 00000 11111 00000 00000 00000','.':'00000 00000 00000 00000 00000 00110 00110',
'[':'01110 01000 01000 01000 01000 01000 01110',']':'01110 00010 00010 00010 00010 00010 01110',
'+':'00000 00100 00100 11111 00100 00100 00000',':':'00000 00100 00100 00000 00100 00100 00000',
'_':'00000 00000 00000 00000 00000 00000 11111'}


def png_bytes(result):
    width,height=1000,620; pixels=bytearray([255])*(width*height*3)
    def pixel(x,y,color):
        x,y=int(x),int(y)
        if 0<=x<width and 0<=y<height: pixels[(y*width+x)*3:(y*width+x)*3+3]=bytes(color)
    for item in drawing(result):
        if item[0]=='text':
            _,x,y,s=item
            for ch in s.upper():
                for dy,row in enumerate(FONT.get(ch,'').split()):
                    for dx,bit in enumerate(row):
                        if bit=='1': pixel(x+dx,y-7+dy,(25,25,25))
                x+=6
        else:
            _,x,y,xx,yy,col=item; color=tuple(bytes.fromhex(col[1:]));steps=max(1,math.ceil(max(abs(xx-x),abs(yy-y))))
            for i in range(steps+1): pixel(x+(xx-x)*i/steps,y+(yy-y)*i/steps,color)
    def chunk(name,data): return struct.pack('!I',len(data))+name+data+struct.pack('!I',zlib.crc32(name+data)&0xffffffff)
    raw=b''.join(b'\0'+pixels[y*width*3:(y+1)*width*3] for y in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')


def export_bytes(result,kind):
    if kind=='json': return (json.dumps(result,indent=2,allow_nan=False)+'\n').encode()
    if kind=='csv': return csv_bytes(result)
    if kind=='svg': return svg_bytes(result)
    if kind=='png': return png_bytes(result)
    raise ValueError('unknown export format')


def save(result,path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(export_bytes(result,path.suffix.lstrip('.')))
