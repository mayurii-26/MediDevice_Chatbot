import { useState } from "react";
import { CATEGORIES } from "../data/questions";

function CategoryDropdown({ setQuestion, onCategoryChange }) {
  const [selected, setSelected] = useState("");

  const handleChange = (e) => {
    const categoryId = e.target.value;
    setSelected(categoryId);

    if (categoryId) {
      const cat = CATEGORIES.find((c) => c.id === categoryId);
      if (cat) {
        setQuestion(`Tell me about ${cat.label}`);
        if (onCategoryChange) onCategoryChange(categoryId);
      }
    } else {
      if (onCategoryChange) onCategoryChange(null);
    }
  };

  const selectedCategory = CATEGORIES.find((c) => c.id === selected);

  return (
    <div>
      <select value={selected} onChange={handleChange}>
        <option value="">Select Category</option>
        {CATEGORIES.map((cat) => (
          <option key={cat.id} value={cat.id}>
            {cat.label}
          </option>
        ))}
      </select>

      {selectedCategory && (
        <div className="subcategory-row">
          {selectedCategory.subcategories.map((sub) => (
            <button
              key={sub}
              className="subcategory-chip"
              onClick={() => setQuestion(`Tell me about ${sub}`)}
            >
              {sub}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default CategoryDropdown;
