#!/bin/bash
set -e

echo "1. Checking Streamlit Frontend Route..."
curl --fail --retry 5 --retry-connrefused --retry-delay 3 http://localhost:8501

echo "2. Checking FastAPI Health Route..."
curl --fail --retry 5 --retry-connrefused --retry-delay 3 http://localhost:8000/health

echo "3. Checking FastAPI Features Route..."
curl --fail --retry 5 --retry-connrefused --retry-delay 3 http://localhost:8000/features

# echo "3. Checking Prometheus Custom Metrics Route..."
# curl --fail --silent http://localhost:8000/metrics | grep "http_requests_total"

echo "4. Simulating E2E Patient Autoimmune Diagnosis Prediction..."
HTTP_STATUS=$(curl -s -o prediction.txt -w "%{http_code}" -X POST http://localhost:8000/predict \
-H "Content-Type: application/json" \
-d '{"ESR": 23.7, "RBC_Count": 4.33, "PLT_Count": 276336, "Hemoglobin": 12.7, "MCH": 26.6, "Sickness_Duration_Months": 43, "Reticulocyte_Count": 1.63, "Monocytes": 3.3, "WBC_Count": 8828, "MPV": 8.4, "MBL_Level": 0.95, "MCV": 84.7, "RDW": 14.6, "C3": 67.4, "Hematocrit": 39.9, "Lymphocytes": 25.8, "MCHC": 31.2, "Neutrophils": 34.6, "Basophils": 0.81, "Eosinophils": 2.3, "Age": 22, "C4": 4.35, "Esbach": 239.6}')

if [ "$HTTP_STATUS" -ne 200 ] || ! grep -q "success" prediction.txt; then
echo "E2E Prediction Test Failed!"
cat prediction.txt
exit 1
fi
echo "E2E Autoimmune Prediction passed successfully!"