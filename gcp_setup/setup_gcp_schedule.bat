@echo on
setlocal

:: Configuration variables (based on your deploy.yaml)
set PROJECT_ID=garmin-syncher-491619
set REGION=europe-west3
set JOB_NAME=garmin-syncher-job
set SCHEDULE_NAME=smartrow-sync-schedule

echo ==^> Verifying gcloud authentication...
call gcloud auth print-access-token --quiet >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo NOTICE: You are not authenticated with gcloud.
    echo Opening browser to authenticate... Please complete the login in your browser.
    call gcloud auth login --update-adc
)
echo ==^> Authentication successful.
echo.

echo ==^> Retrieving project number for %PROJECT_ID%...
for /f "tokens=*" %%i in ('call gcloud projects describe %PROJECT_ID% --format="value(projectNumber)"') do set PROJECT_NUMBER=%%i
set SERVICE_ACCOUNT=%PROJECT_NUMBER%-compute@developer.gserviceaccount.com

echo ==^> Using Default Compute Service Account: %SERVICE_ACCOUNT%
echo.

echo ==^> 1/3: Granting Secret Manager Secret Accessor role...
call gcloud projects add-iam-policy-binding %PROJECT_ID% ^
    --member="serviceAccount:%SERVICE_ACCOUNT%" ^
    --role="roles/secretmanager.secretAccessor" ^
    --condition=None
echo.

echo ==^> 2/3: Granting Storage Object Admin role...
call gcloud projects add-iam-policy-binding %PROJECT_ID% ^
    --member="serviceAccount:%SERVICE_ACCOUNT%" ^
    --role="roles/storage.objectAdmin" ^
    --condition=None
echo.

echo ==^> 3/3: Creating the Cloud Scheduler job...
:: If the scheduler already exists, you can prepend this with a delete command or use `update` instead
:: call gcloud scheduler jobs delete %SCHEDULE_NAME% --location=%REGION% --quiet
call gcloud scheduler jobs create http %SCHEDULE_NAME% ^
  --location=%REGION% ^
  --schedule="0 10,12,15 * * *" ^
  --time-zone="Europe/Berlin" ^
  --uri="https://%REGION%-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/%PROJECT_ID%/jobs/%JOB_NAME%:run" ^
  --http-method=POST ^
  --oauth-service-account-email=%SERVICE_ACCOUNT%

echo.
echo ==^> Setup complete!
echo Cloud Job '%JOB_NAME%' will now automatically trigger at 10am, 12pm, and 3pm CET.
