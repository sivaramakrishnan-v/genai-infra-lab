import { useState } from "react";

function AnalyzeButton({ files }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleAnalyze = async () => {
    if (files.length === 0) {
      alert("Please select at least one file.");
      return;
    }

    setLoading(true);

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    try {
      const response = await fetch("http://localhost:5000/api/analyze", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      setResult(data);

    } catch (error) {
      console.error("API error:", error);
      alert("Error analyzing logs. Check backend.");
    }

    setLoading(false);
  };

  return (
    <div style={{ padding: 20 }}>
      <button
        onClick={handleAnalyze}
        disabled={loading}
        style={{
          padding: "10px 20px",
          cursor: "pointer",
        }}
      >
        {loading ? "Analyzing..." : "Analyze Logs"}
      </button>

      {result && (
        <pre style={{ marginTop: 20 }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default AnalyzeButton;
