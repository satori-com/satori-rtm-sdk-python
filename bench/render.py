#!/usr/bin/env python3

import os
import statistics as s
import subprocess

def main():
    render('subscribe')
    render('publish')

def render(publish_or_subscribe):
    benches_by_size = {}
    names = set()
    sizes = set()
    for name, size, rps, err in discover_benches(publish_or_subscribe):
        names.add(name)
        sizes.add(size)
        if size in benches_by_size:
            benches_by_size[size][name] = (rps, err)
        else:
            benches_by_size[size] = {name: (rps, err)}

    names = sorted(list(names))
    sizes = sorted(list(sizes))

    with open(publish_or_subscribe + '.dat', 'w') as fo:
        print('size', end='', file=fo)
        for name in names:
            print('', name, end='', file=fo)
        for name in names:
            print('', name, end='', file=fo)
        print('', file=fo)
        for size in sizes:
            benches = benches_by_size[size]
            print(size, end='', file=fo)
            for name in names:
                print('', benches[name][0], end='', file=fo)
            for name in names:
                print('', benches[name][1], end='', file=fo)
            print('', file=fo)

    subprocess.check_call(['gnuplot', publish_or_subscribe + '.plot'])


def discover_benches(publish_or_subscribe):
    for f in os.listdir(os.curdir):
        if not f.startswith(publish_or_subscribe + '-'):
            continue
        with open(f) as fi:
            datalines = [l.split() for l in fi.readlines() if l[0].isdigit()]
            rpss = [float(d[1]) for d in datalines]
            rps_avg = s.mean(rpss)
            rps_stddev = s.pstdev(rpss)

            parts = f.split('-')
            size = int(parts[-1])

            yield ('-'.join(parts[1:-1]), size, rps_avg, rps_stddev)


if __name__ == '__main__':
    main()
