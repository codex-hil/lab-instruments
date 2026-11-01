"""Independent scalar Decimal controls; no AllanTools, NumPy, or TimeLab code."""
from decimal import Decimal, localcontext

def statistics(values, m, dt):
    with localcontext() as ctx:
        ctx.prec=60
        x=[Decimal.from_float(float(v)) for v in values]
        n=len(x); tau=Decimal(str(dt))*m
        d2=[x[i+2*m]-2*x[i+m]+x[i] for i in range(n-2*m)]
        d3=[x[i+3*m]-3*x[i+2*m]+3*x[i+m]-x[i] for i in range(n-3*m)]
        def rms(a,den):
            return float((sum((v*v for v in a),Decimal(0))/len(a)/den).sqrt())
        prefix=[Decimal(0)]
        for v in d2:prefix.append(prefix[-1]+v)
        averaged=[(prefix[i+m]-prefix[i])/m for i in range(n-3*m+1)]
        md=rms(averaged,2*tau*tau)
        return {'adev':rms(d2[::m],2*tau*tau), 'oadev':rms(d2,2*tau*tau),
                'hdev':rms(d3[::m],6*tau*tau), 'ohdev':rms(d3,6*tau*tau),
                'mdev':md,'tdev':float(tau/Decimal(3).sqrt())*md,
                'mtie':float(max(max(x[i:i+m+1])-min(x[i:i+m+1]) for i in range(n-m)))}
