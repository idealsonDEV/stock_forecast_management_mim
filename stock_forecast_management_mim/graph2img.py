import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatch
from io import BytesIO

def tobinary(y,y2,x0,y0,daterange,string):
	fig = plt.figure()
	ax = fig.add_subplot(111)

	x = daterange

	x2 = daterange[2:14]


	plt.plot(x0, y0, 'r-', lw=2)

	maxy = max(y)

	plt.xlim([0, 18])
	plt.ylim([0, maxy])

	plt.plot(x, y)
	plt.plot(x2, y2)
	for i,j in zip(x,y):
	    ax.annotate(str(j),xy=(i,j))
	plt.xlabel("Trimetre")
	plt.ylabel("Qunatite")
	plt.title(string)

	figfile = BytesIO()
	plt.savefig(figfile, format='png')

	return figfile.getvalue()