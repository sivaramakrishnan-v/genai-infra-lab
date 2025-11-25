import { useState } from "react";
import FilePicker from "../components/FilePicker";
import FileList from "../components/FileList";
import AnalyzeButton from "../components/AnalyzeButton";

function Analyze() {
  const [files, setFiles] = useState([]);

  return (
    <div style={{ padding: 20 }}>
      <h2>Analyze Logs</h2>

      <FilePicker onFilesSelected={setFiles} />
      <FileList files={files} />
      <AnalyzeButton files={files} />
    </div>
  );
}

export default Analyze;
