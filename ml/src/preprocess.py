import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from imblearn.combine import SMOTEENN

def split_data(X, y):
    """Splits data with 20% test size."""
    return train_test_split(X, y, test_size=0.2, random_state=42)

def scale_data(X_train, X_test, scaler_save_path):
    """Scales only numeric columns and recombines with the rest."""
    scaler = StandardScaler()
    
    # Identify numeric columns (> 2 unique values)
    num_cols = [col for col in X_train.columns if X_train[col].dtype in ['int64', 'float64'] and X_train[col].dropna().nunique() > 2]
    other_cols = [col for col in X_train.columns if col not in num_cols]
    
    X_train_scaled = scaler.fit_transform(X_train[num_cols])
    X_test_scaled = scaler.transform(X_test[num_cols])
    
    # Recombine
    X_train_final = pd.DataFrame(np.hstack([X_train_scaled, X_train[other_cols].values]), columns=num_cols + other_cols)
    X_test_final = pd.DataFrame(np.hstack([X_test_scaled, X_test[other_cols].values]), columns=num_cols + other_cols)
    
    joblib.dump(scaler, scaler_save_path)
    return X_train_final, X_test_final

def balance_training_data(X_train, y_train):
    """Applies SMOTEENN balancing exclusively to the training set."""
    smoteenn = SMOTEENN(random_state=42)
    X_train_balanced, y_train_balanced = smoteenn.fit_resample(X_train, y_train)
    return X_train_balanced, y_train_balanced