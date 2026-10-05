import React from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

function App() {
  return (
    <main>
      <p className="eyebrow">Nutrition Planner</p>
      <h1>Foundation is running.</h1>
      <p>The onboarding and daily planning experience will be built on this shell.</p>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

