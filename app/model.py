"""Keep the validation-selected threshold inside the registered estimator."""
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin

class ThresholdClassifier(ClassifierMixin, BaseEstimator):
    def __init__(self, forest, threshold=0.5):
        self.forest=forest
        self.threshold=threshold
        self.classes_=forest.classes_
        self.n_features_in_=forest.n_features_in_
    def fit(self,X,y):
        self.forest.fit(X,y)
        self.classes_=self.forest.classes_
        self.n_features_in_=self.forest.n_features_in_
        return self
    def predict_proba(self,X):return self.forest.predict_proba(X)
    def predict(self,X):return (self.predict_proba(X)[:,list(self.classes_).index(1)]>=self.threshold).astype(int)
    @property
    def feature_importances_(self):return self.forest.feature_importances_
