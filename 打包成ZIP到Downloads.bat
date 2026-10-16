@echo off
chcp 65001 >nul
set SRC=%~dp0
set DEST=%USERPROFILE%\Downloads\bli-batch-downloader-v1.0.0.zip
echo 正在打包到：
echo %DEST%
powershell -NoProfile -Command "Compress-Archive -Path '%SRC%*' -DestinationPath '%DEST%' -Force"
if exist "%DEST%" (
  echo.
  echo 完成。可用檔案總管開啟 Downloads 取得 zip。
  explorer "%USERPROFILE%\Downloads"
) else (
  echo 打包失敗。
)
pause
