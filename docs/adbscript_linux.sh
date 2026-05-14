#!/bin/sh 

cp -aR keys/* ~/.android/ 

echo "-> key files was copied!" 

sed '/ADB_VENDOR_KEYS/d' ~/.bashrc > bashrc 
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/us4pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/us4kvjap/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/us4kv/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/sx2h/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/sx2ev/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/sx2/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/sv1/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/sg2pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/rg3perus/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/rg3pemy26mes/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/rg3pemy26/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/rg3pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/rg3kv/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/nx4pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/nq5pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/nh2na/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/nh2jap/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/nh2/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/ne1knjap/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/ne1kn/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/ne1jap/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/ne1/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/mx5h/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/mx5/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/mv1my26/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/mv1/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/mq4pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/me/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/lx3t/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/lx3nat/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/lx3na/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/lx3/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/ka4pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jx1pet/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jx1perus/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jx1pemy26mes/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jx1pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jw1peuk/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jw1peeur/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jw1pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jk1perus/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jk1pemy26mes/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jk1pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jk1kv/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jg1rus/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jg1na/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/jg1/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/gn7t/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/gn7pet/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/gn7pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/gn7my24/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/gn7h/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/gn7/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/gl3pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/dn8pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/dl3pe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/dcm_dev/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/cvpe/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/ct1/adbkey:" >> bashrc
echo "export ADB_VENDOR_KEYS+=${HOME}/.android/ce1pe/adbkey:" >> bashrc

mv bashrc ~/.bashrc 

if [ $? -eq 0 ]; then 

    echo "-> adb server will be restarted!" 

    adb kill-server 

else 

    echo "Can't find adb's process id." 

fi 

