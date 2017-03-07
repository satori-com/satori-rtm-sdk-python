set output "subscribe.png"
set terminal png size 1024,768

set style fill solid border rgb "black"
set style data histogram
set style histogram errorbars gap 3

set title "Channel data"
set xlabel "message size"
set ylabel "rps"
set yrange [0 : *]
set key autotitle columnhead

plot "subscribe.dat" using 2:6:xtic(1), \
    '' using 3:7:xtic(1), \
    '' using 4:8:xtic(1), \
    '' using 5:9:xtic(1)