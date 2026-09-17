import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import RFECV

def perform_rfecv(X_train, y_train, features_save_path):
    """Selects optimal features using RFECV with a Random Forest estimator."""
    estimator = RandomForestClassifier(n_estimators=100, random_state=42)
    rfecv = RFECV(estimator=estimator, step=1, cv=5, scoring='accuracy')
    rfecv.fit(X_train, y_train)
    
    selected_features = list(X_train.columns[rfecv.support_])
    joblib.dump(selected_features, features_save_path)
    
    return selected_features