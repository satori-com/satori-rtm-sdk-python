set output "publish.png"
set terminal png size 1024,768

set style fill solid border rgb "black"
set style data histogram
set style histogram errorbars gap 3

set title "Publish"
set xlabel "message size"
set ylabel "rps"
set yrange [0 : *]
set key autotitle columnhead

plot "publish.dat" using 2:10:xtic(1), \
    '' using 3:11:xtic(1), \
    '' using 4:12:xtic(1), \
    '' using 5:13:xtic(1), \
    '' using 6:14:xtic(1), \
    '' using 7:15:xtic(1), \
    '' using 8:16:xtic(1), \
    '' using 9:17:xtic(1)