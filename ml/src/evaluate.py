from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score

def evaluate_model(model, X_test, y_test):
    """Evaluates model performance and returns key metrics."""
    y_pred = model.predict(X_test)
    y_probs = model.predict_proba(X_test) if hasattr(model, "predict_proba") else None
    
    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_test, y_pred),
        "f1_weighted": f1_score(y_test, y_pred, average='weighted')
    }
    
    if y_probs is not None:
        metrics["roc_auc"] = roc_auc_score(y_test, y_probs, multi_class='ovr')
        
    return metrics