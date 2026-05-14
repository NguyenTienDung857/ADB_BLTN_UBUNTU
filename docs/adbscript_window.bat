@ECHO OFF 

cd \%~dp0 

xcopy /Y /E /K keys\* %USERPROFILE%\.android 

echo COPY DONE! 

setx ADB_VENDOR_KEYS %USERPROFILE%\.android\ce1pe\adbkey;%USERPROFILE%\.android\ct1\adbkey;%USERPROFILE%\.android\cvpe\adbkey;%USERPROFILE%\.android\dcm_dev\adbkey;%USERPROFILE%\.android\dl3pe\adbkey;%USERPROFILE%\.android\dn8pe\adbkey;%USERPROFILE%\.android\gl3pe\adbkey;%USERPROFILE%\.android\gn7\adbkey;%USERPROFILE%\.android\gn7h\adbkey;%USERPROFILE%\.android\gn7my24\adbkey;%USERPROFILE%\.android\gn7pe\adbkey;%USERPROFILE%\.android\gn7pet\adbkey;%USERPROFILE%\.android\gn7t\adbkey;%USERPROFILE%\.android\jg1\adbkey;%USERPROFILE%\.android\jg1na\adbkey;%USERPROFILE%\.android\jg1rus\adbkey;%USERPROFILE%\.android\jk1kv\adbkey;%USERPROFILE%\.android\jk1pe\adbkey;%USERPROFILE%\.android\jk1pemy26mes\adbkey;%USERPROFILE%\.android\jk1perus\adbkey;%USERPROFILE%\.android\jw1pe\adbkey;%USERPROFILE%\.android\jw1peeur\adbkey;%USERPROFILE%\.android\jw1peuk\adbkey;%USERPROFILE%\.android\jx1pe\adbkey;%USERPROFILE%\.android\jx1pemy26mes\adbkey;%USERPROFILE%\.android\jx1perus\adbkey;%USERPROFILE%\.android\jx1pet\adbkey;%USERPROFILE%\.android\ka4pe\adbkey;%USERPROFILE%\.android\lx3\adbkey;%USERPROFILE%\.android\lx3na\adbkey;%USERPROFILE%\.android\lx3nat\adbkey;%USERPROFILE%\.android\lx3t\adbkey;%USERPROFILE%\.android\me\adbkey;%USERPROFILE%\.android\mq4pe\adbkey;%USERPROFILE%\.android\mv1\adbkey;%USERPROFILE%\.android\mv1my26\adbkey;%USERPROFILE%\.android\mx5\adbkey;%USERPROFILE%\.android\mx5h\adbkey;%USERPROFILE%\.android\ne1\adbkey;%USERPROFILE%\.android\ne1jap\adbkey;%USERPROFILE%\.android\ne1kn\adbkey;%USERPROFILE%\.android\ne1knjap\adbkey;%USERPROFILE%\.android\nh2\adbkey;%USERPROFILE%\.android\nh2jap\adbkey;%USERPROFILE%\.android\nh2na\adbkey;%USERPROFILE%\.android\nq5pe\adbkey;%USERPROFILE%\.android\nx4pe\adbkey;%USERPROFILE%\.android\rg3kv\adbkey;%USERPROFILE%\.android\rg3pe\adbkey;%USERPROFILE%\.android\rg3pemy26\adbkey;%USERPROFILE%\.android\rg3pemy26mes\adbkey;%USERPROFILE%\.android\rg3perus\adbkey;%USERPROFILE%\.android\sg2pe\adbkey;%USERPROFILE%\.android\sv1\adbkey;%USERPROFILE%\.android\sx2\adbkey;%USERPROFILE%\.android\sx2ev\adbkey;%USERPROFILE%\.android\sx2h\adbkey;%USERPROFILE%\.android\us4kv\adbkey;%USERPROFILE%\.android\us4kvjap\adbkey;%USERPROFILE%\.android\us4pe\adbkey;

Pause 

