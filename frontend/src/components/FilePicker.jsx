import { useState } from "react";

function FilePicker({ onFilesSelected }) {
  const [selectedFiles, setSelectedFiles] = useState([]);

  const handleChange = (e) => {
    const files = Array.from(e.target.files);
    setSelectedFiles(files);
    onFilesSelected(files); // send files to parent (App)
  };

  return (
    <div style={{ padding: "20px" }}>
      <input
        type="file"
        multiple
        onChange={handleChange}
        style={{ marginBottom: "10px" }}
      />

      {selectedFiles.length > 0 && (
        <p>{selectedFiles.length} file(s) selected</p>
      )}
    </div>
  );
}

export default FilePicker;
