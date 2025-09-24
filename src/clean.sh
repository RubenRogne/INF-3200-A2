#!/bin/sh

export PATH=/bin:/usr/bin

ME=`id -un`

if [ x$ME = xroot ]
then
	echo "Do not run $0 as root"
	exit
fi

exec 2> /dev/null

AN=`cat /share/compute-nodes.txt; echo ificluster`
TN=`hostname -s`

for N in `echo $AN | sed -e "s/$TN//"`
do
        ssh -o ConnectTimeout=1 -o ConnectionAttempts=1 -x $N "killall -s 9 -u $ME > /dev/null 2>&1" &
	# sleep 0.1
done
wait
# killall -s 9 -u $ME > /dev/null 2>&1
killall -s 9 -u $ME -v -e -r '^(?!bash|ssh)'
