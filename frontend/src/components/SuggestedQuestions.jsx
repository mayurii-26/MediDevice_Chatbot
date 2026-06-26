import { suggestedQuestions, CATEGORY_QUESTIONS } from "../data/questions";

function SuggestedQuestions({ onSelect, activeCategory }) {
  const questions = activeCategory && CATEGORY_QUESTIONS[activeCategory]
    ? CATEGORY_QUESTIONS[activeCategory]
    : suggestedQuestions;

  return (
    <div>
      {activeCategory && (
        <p className="questions-category-label">
          Showing questions for: <strong>{activeCategory.replace(/([A-Z])/g, " $1").trim()}</strong>
        </p>
      )}
      <div className="questions-wrap">
        {questions.map((q, index) => (
          <button
            key={index}
            className="question-btn"
            onClick={() => onSelect(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

export default SuggestedQuestions;
