import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC

def train_random_forest(X_train, y_train, model_save_path):
    """Trains and saves the Random Forest model."""
    model = RandomForestClassifier(n_estimators=70, max_depth=18, min_samples_split=10, random_state=42)
    model.fit(X_train, y_train)
    joblib.dump(model, model_save_path)
    return model

def train_svc(X_train, y_train, model_save_path):
    """Trains and saves the Support Vector Classifier."""
    model = SVC(C=5, kernel='rbf', gamma=0.05, class_weight='balanced', random_state=42)
    model.fit(X_train, y_train)
    joblib.dump(model, model_save_path)
    return model