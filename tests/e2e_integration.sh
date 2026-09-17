#!/bin/bash
set -e

echo "1. Checking Streamlit Frontend Route..."
curl --fail --retry 5 --retry-connrefused --retry-delay 3 http://localhost:8501

echo "2. Checking FastAPI Health Route..."
curl --fail --retry 5 --retry-connrefused --retry-delay 3 http://localhost:8000/health

echo "3. Checking FastAPI Features Route..."
curl --fail --retry 5 --retry-connrefused --retry-delay 3 http://localhost:8000/features

echo "4. Simulating E2E Patient Autoimmune Diagnosis Prediction..."
HTTP_STATUS=$(curl -s -o prediction.txt -w "%{http_code}" -X POST http://localhost:8000/predict \
-H "Content-Type: application/json" \
-d '{"ESR": 23.7, "RBC_Count": 4.33, "PLT_Count": 276336, "Hemoglobin": 12.7, "MCH": 26.6, "Sickness_Duration_Months": 43, "Reticulocyte_Count": 1.63, "Monocytes": 3.3, "WBC_Count": 8828, "MPV": 8.4, "MBL_Level": 0.95, "MCV": 84.7, "RDW": 14.6, "C3": 67.4, "Hematocrit": 39.9, "Lymphocytes": 25.8, "MCHC": 31.2, "Neutrophils": 34.6, "Basophils": 0.81, "Eosinophils": 2.3, "Age": 22, "C4": 4.35, "Esbach": 239.6, "crp": 5.0, "clinical_symptoms_count": 2, "ana": 1, "rheumatoid_factor": 15.0, "acpa": 10.0, "anti_tpo": 12.0, "anti_tg": 20.0, "anti_sma": 5.0, "low_grade_fever": 1, "dizziness": 0, "rashes_and_skin_lesions": 1, "stiffness_in_the_joints": 0, "brittle_hair_or_hair_loss": 0, "general_unwell_feeling": 1, "gender": 1}')

if [ "$HTTP_STATUS" -ne 200 ] || ! grep -q "success" prediction.txt; then
echo "E2E Prediction Test Failed!"
cat prediction.txt
exit 1
fi
echo "E2E Autoimmune Prediction passed successfully!"
