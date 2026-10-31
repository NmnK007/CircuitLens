



call %PREFIX%\bin\ngspice_con.exe --version
IF %ERRORLEVEL% NEQ 0 exit /B 1
call %PREFIX%\bin\ngspice_con.exe -b -r raw.out test-files\test.cir
IF %ERRORLEVEL% NEQ 0 exit /B 1
exit /B 0
