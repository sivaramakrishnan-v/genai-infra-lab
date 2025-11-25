function FileList({ files }) {
  if (files.length === 0) {
    return null; // do not render anything if empty
  }

  return (
    <ul style={{ padding: "20px" }}>
      {files.map((file) => (
        <li key={file.name}>{file.name}</li>
      ))}
    </ul>
  );
}

export default FileList;
