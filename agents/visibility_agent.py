import json
from typing import Dict, Any
from pydantic import BaseModel, Field

# AEO Table Weights
AEO_WEIGHTS = {
    'Content_Quality_And_Depth': 9.25,
    'Trustworthiness_And_Credibility': 8.75,
    'Content_Relevance': 8.75,
    'Citations_And_Mentions_In_Trusted_Sources': 8.5,
    'Topical_Authority_And_Expertise': 8.5,
    'Search_Engine_Rankings_Bing_Google': 7.5,
    'Verifiable_Performance_Metrics': 7.5,
    'Sentiment_Analysis': 7.25,
    'Data_Frequency_And_Consistency': 7.25,
    'Social_Proof_And_Reviews': 7.25,
    'Structured_Data_Schema_Markup': 6.25,
    'Content_Freshness_And_Timeliness': 6.0,
    'Technical_Performance_Speed_Mobile': 5.75,
    'Localization': 5.75,
    'Social_Signals': 4.75
}

MODEL_WEIGHTS = {
    'gpt': {
        'Content_Quality_And_Depth': 10,
        'Trustworthiness_And_Credibility': 10,
        'Content_Relevance': 9,
        'Citations_And_Mentions_In_Trusted_Sources': 7,
        'Topical_Authority_And_Expertise': 9,
        'Search_Engine_Rankings_Bing_Google': 7,
        'Verifiable_Performance_Metrics': 8,
        'Sentiment_Analysis': 8,
        'Data_Frequency_And_Consistency': 7,
        'Social_Proof_And_Reviews': 8,
        'Structured_Data_Schema_Markup': 6,
        'Content_Freshness_And_Timeliness': 7,
        'Technical_Performance_Speed_Mobile': 6,
        'Localization': 6,
        'Social_Signals': 6
    },
    'perplexity': {
        'Content_Quality_And_Depth': 10,
        'Trustworthiness_And_Credibility': 9,
        'Content_Relevance': 10,
        'Citations_And_Mentions_In_Trusted_Sources': 10,
        'Topical_Authority_And_Expertise': 8,
        'Search_Engine_Rankings_Bing_Google': 8,
        'Verifiable_Performance_Metrics': 7,
        'Sentiment_Analysis': 7,
        'Data_Frequency_And_Consistency': 10,
        'Social_Proof_And_Reviews': 7,
        'Structured_Data_Schema_Markup': 7,
        'Content_Freshness_And_Timeliness': 6,
        'Technical_Performance_Speed_Mobile': 6,
        'Localization': 6,
        'Social_Signals': 5
    },
    'claude': {
        'Content_Quality_And_Depth': 8,
        'Trustworthiness_And_Credibility': 9,
        'Content_Relevance': 8,
        'Citations_And_Mentions_In_Trusted_Sources': 9,
        'Topical_Authority_And_Expertise': 8,
        'Search_Engine_Rankings_Bing_Google': 6,
        'Verifiable_Performance_Metrics': 9,
        'Sentiment_Analysis': 8,
        'Data_Frequency_And_Consistency': 9,
        'Social_Proof_And_Reviews': 8,
        'Structured_Data_Schema_Markup': 6,
        'Content_Freshness_And_Timeliness': 6,
        'Technical_Performance_Speed_Mobile': 6,
        'Localization': 6,
        'Social_Signals': 5
    },
    'gemini': {
        'Content_Quality_And_Depth': 9,
        'Trustworthiness_And_Credibility': 7,
        'Content_Relevance': 8,
        'Citations_And_Mentions_In_Trusted_Sources': 8,
        'Topical_Authority_And_Expertise': 7,
        'Search_Engine_Rankings_Bing_Google': 9,
        'Verifiable_Performance_Metrics': 6,
        'Sentiment_Analysis': 6,
        'Data_Frequency_And_Consistency': 3,
        'Social_Proof_And_Reviews': 6,
        'Structured_Data_Schema_Markup': 6,
        'Content_Freshness_And_Timeliness': 5,
        'Technical_Performance_Speed_Mobile': 5,
        'Localization': 5,
        'Social_Signals': 3
    }
}

Industry_avg = {
    'Content_Quality_And_Depth': 95,
    'Trustworthiness_And_Credibility': 85,
    'Content_Relevance': 85,
    'Citations_And_Mentions_In_Trusted_Sources': 95,
    'Topical_Authority_And_Expertise': 85,
    'Search_Engine_Rankings_Bing_Google': 85,
    'Verifiable_Performance_Metrics': 80,
    'Sentiment_Analysis': 85,
    'Data_Frequency_And_Consistency': 80,
    'Social_Proof_And_Reviews': 85,
    'Structured_Data_Schema_Markup': 80,
    'Content_Freshness_And_Timeliness': 80,
    'Technical_Performance_Speed_Mobile': 85,
    'Localization': 85,
    'Social_Signals': 85
}
class AEOEvaluationResult(BaseModel):
    score_percentage: float
    industry_avg_percentage: float
    visibility_grade: str
    detailed: Dict[str, Dict[str, Any]]
    model_scores: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class AEOEvaluatorAgent:
    def __init__(self, weights: Dict[str, float]):
        self.weights = weights

    def evaluate(self, scores: Dict[str, int]) -> AEOEvaluationResult:
        print(self.weights.values())
        total_possible = sum(weight * 100 for weight in self.weights.values())
        weighted_sum = 0
        ind_weighted_sum = 0
        details = {}

        for var, weight in self.weights.items():
            score = scores.get(var, 0)
            ind_score = Industry_avg.get(var, 0)
            weighted_sum += score * weight
            ind_weighted_sum += ind_score*weight

            # Calculate variation only if score is not zero to avoid division by zero
            variation = ((score - ind_score) / score * 100) if score != 0 else 0
            
            details[var] = {
                "score": score,
                "industry_avg": ind_score,
                "variation": round(variation, 2)
            }

        score_percentage = (weighted_sum / total_possible) * 100
        industry_avg_percentage=(ind_weighted_sum/total_possible)*100

        if score_percentage >= 85:
            grade = "A+"
        elif score_percentage >= 75:
            grade = "A"
        elif score_percentage >= 65:
            grade = "B"
        elif score_percentage >= 50:
            grade = "C"
        else:
            grade = "D"

        model_scores = self.evaluate_all_models(scores)

        return AEOEvaluationResult(
            score_percentage=round(score_percentage, 2),
            industry_avg_percentage=industry_avg_percentage,
            visibility_grade=grade,
            detailed=details,
            model_scores=model_scores
        )

    def evaluate_all_models(self, scores: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
        results = {}
        for model, weights in MODEL_WEIGHTS.items():
            total_possible = sum(w * 100 for w in weights.values())
            weighted_sum = 0
            ind_weighted_sum = 0

            for var, weight in weights.items():
                score = scores.get(var, 0)
                ind_score = Industry_avg.get(var, 0)
                weighted_sum += score * weight
                ind_weighted_sum += ind_score * weight
            # print(weighted_sum)
            # print(total_possible)
            score_pct = (weighted_sum / total_possible) * 100
            ind_score_pct = (ind_weighted_sum / total_possible) * 100

            if score_pct >= 85:
                grade = "A+"
            elif score_pct >= 75:
                grade = "A"
            elif score_pct >= 65:
                grade = "B"
            elif score_pct >= 50:
                grade = "C"
            else:
                grade = "D"

            results[model] = {
                "score_percentage": round(score_pct, 2),
                "industry_avg_percentage": round(ind_score_pct, 2),
                "visibility_grade": grade
            }
        return results

    def run_visibility_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        print("Running visibility node")
        periodic_table_report = state.get("periodic_table_report", {})

        if not periodic_table_report:
            print("Error: periodic_table_report is missing in the state.")
            return state

        # If periodic_table_report is a PeriodicTable object, convert it to a dict
        if hasattr(periodic_table_report, 'dict'):
            scores = periodic_table_report.dict()
        else:
            scores = periodic_table_report
        print(scores)
        evaluation_result = self.evaluate(scores)

        state["visibility_report"] = evaluation_result.dict()
        with open("output/visibility.json", "w") as f:
            json.dump(evaluation_result.dict(), f, indent=4)
            
        return state
