import numpy
from numpy import sqrt, mean

y = numpy.loadtxt("half_filt.dat")
npt = len(y)
print('read %d points, expected 238' % npt)
ix = numpy.arange(npt) + 1
s = numpy.sin((ix+9.0)*.0081*2*16)
lf1 = numpy.polyfit(s, y, 1)
oamp = abs(lf1[0])
print('actual amplitude %8.1f, expected about 200000' % oamp)
erry = y-lf1[0]*s
err = numpy.std(erry)
print('DC offset     %.4f bits, expected about 0' % mean(erry))

nom_err = sqrt(1.0**2+1/12)*0.66787
print('std deviation %.4f bits, expected about %.4f' % (err, nom_err))
print('excess noise  %.4f bits' % sqrt(err**2-nom_err**2))
if ((npt > 230) and (oamp > 199800) and (oamp < 200000) and (abs(mean(erry)) < 0.01) and (err < sqrt(nom_err**2 + 0.3**2))):
    print("PASS")
else:
    print("FAIL")
    exit(1)
