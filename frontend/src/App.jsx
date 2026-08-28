import { useRef, useState } from "react";

const API_BASE_URL = "http://127.0.0.1:8000";

function App() {
  const fileInputRef = useRef(null);

  const [selectedFile, setSelectedFile] = useState(null);

  const [uploadedDocument, setUploadedDocument] =
    useState(null);

  const [analysis, setAnalysis] = useState(null);

  const [selectedReviewIds, setSelectedReviewIds] =
    useState([]);

  const [isAnalyzing, setIsAnalyzing] =
    useState(false);

  const [isRedacting, setIsRedacting] =
    useState(false);

  const [analysisStage, setAnalysisStage] =
    useState("");

  const [redactionSuccess, setRedactionSuccess] =
    useState(false);

  const [error, setError] = useState("");

  const handleFileChange = (event) => {
    const file = event.target.files[0];

    if (!file) {
      return;
    }

    setSelectedFile(file);
    setUploadedDocument(null);
    setAnalysis(null);
    setSelectedReviewIds([]);
    setRedactionSuccess(false);
    setAnalysisStage("");
    setError("");
  };

  const handleChooseFile = () => {
    fileInputRef.current?.click();
  };

  const handleAnalyze = async () => {
    if (!selectedFile || isAnalyzing) {
      return;
    }

    setIsAnalyzing(true);
    setAnalysisStage("uploading");
    setRedactionSuccess(false);
    setError("");
    setUploadedDocument(null);
    setAnalysis(null);
    setSelectedReviewIds([]);

    try {
      const formData = new FormData();

      formData.append(
        "file",
        selectedFile
      );

      const uploadResponse = await fetch(
        `${API_BASE_URL}/api/documents`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!uploadResponse.ok) {
        const uploadError =
          await uploadResponse.json();

        throw new Error(
          uploadError.detail ||
            "Document upload failed."
        );
      }

      const uploadedData =
        await uploadResponse.json();

      setUploadedDocument(uploadedData);

      setAnalysisStage("analyzing");

      const analyzeResponse = await fetch(
        `${API_BASE_URL}/api/documents/${uploadedData.id}/analyze`
      );

      if (!analyzeResponse.ok) {
        const analyzeError =
          await analyzeResponse.json();

        throw new Error(
          analyzeError.detail ||
            "Document analysis failed."
        );
      }

      const analysisResult =
        await analyzeResponse.json();

      setAnalysis(analysisResult);
    } catch (error) {
      setError(error.message);
    } finally {
      setIsAnalyzing(false);
      setAnalysisStage("");
    }
  };

  const handleReviewToggle = (findingId) => {
    setSelectedReviewIds((current) => {
      if (current.includes(findingId)) {
        return current.filter(
          (id) => id !== findingId
        );
      }

      return [
        ...current,
        findingId,
      ];
    });
  };

  const handleCreateRedactedPdf = async () => {
    if (
      !uploadedDocument ||
      isRedacting
    ) {
      return;
    }

    setIsRedacting(true);
    setRedactionSuccess(false);
    setError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/documents/${uploadedDocument.id}/redact-selected`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            selected_finding_ids:
              selectedReviewIds,
          }),
        }
      );

      if (!response.ok) {
        const errorData =
          await response.json();

        throw new Error(
          errorData.detail ||
            "Redaction failed."
        );
      }

      const blob =
        await response.blob();

      const url =
        window.URL.createObjectURL(
          blob
        );

      const link =
        window.document.createElement(
          "a"
        );

      link.href = url;

      link.download =
        `privacylens-redacted-${uploadedDocument.id}.pdf`;

      window.document.body.appendChild(
        link
      );

      link.click();
      link.remove();

      window.URL.revokeObjectURL(url);

      setRedactionSuccess(true);
    } catch (error) {
      setError(error.message);
    } finally {
      setIsRedacting(false);
    }
  };

  const handleAnalyzeAnother = () => {
    setSelectedFile(null);
    setUploadedDocument(null);
    setAnalysis(null);
    setSelectedReviewIds([]);
    setRedactionSuccess(false);
    setAnalysisStage("");
    setError("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const formatConfidence = (
    confidence
  ) => {
    return `${Math.round(
      confidence * 100
    )}%`;
  };

  const autoRedactCount =
    analysis?.findings.filter(
      (finding) =>
        finding.redaction_action ===
        "AUTO_REDACT"
    ).length || 0;

  const reviewFindings =
    analysis?.findings.filter(
      (finding) =>
        finding.redaction_action ===
        "REVIEW"
    ) || [];

  const reviewCount =
    reviewFindings.length;

  const selectedReviewCount =
    selectedReviewIds.length;

  const handleSelectAllReview = () => {
    const reviewIds =
      reviewFindings
        .map(
          (finding) =>
            finding.finding_id
        )
        .filter(Boolean);

    setSelectedReviewIds(
      reviewIds
    );
  };

  const handleClearReview = () => {
    setSelectedReviewIds([]);
  };

  return (
    <div className="app">
      <header className="navbar">
        <div className="brand">
          <div className="brand-icon">
            P
          </div>

          <div>
            <div className="brand-name">
              PrivacyLens
            </div>

            <div className="brand-subtitle">
              AI Document Privacy
            </div>
          </div>
        </div>

        <div className="status-badge">
          <span className="status-dot" />
          Local processing
        </div>
      </header>

      <main className="main">
        <section className="hero">
          <div className="eyebrow">
            PRIVACY-AWARE DOCUMENT
            ANALYSIS
          </div>

          <h1>
            Find sensitive data.
            <br />

            <span>
              Redact with confidence.
            </span>
          </h1>

          <p>
            PrivacyLens detects
            sensitive information in
            documents using rule-based
            validation and Turkish AI
            entity recognition.
          </p>
        </section>

        <section className="workspace">
          <div className="upload-card">
            <div className="upload-icon">
              ↑
            </div>

            <h2>
              Upload a document
            </h2>

            <p>
              Select a PDF to scan for
              personal and sensitive
              information.
            </p>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              hidden
              onChange={
                handleFileChange
              }
            />

            <button
              className="primary-button"
              onClick={
                handleChooseFile
              }
              disabled={isAnalyzing}
            >
              Choose PDF
            </button>

            {selectedFile && (
              <div className="selected-file">
                <div className="file-icon">
                  PDF
                </div>

                <div>
                  <strong>
                    {
                      selectedFile.name
                    }
                  </strong>

                  <span>
                    {(
                      selectedFile.size /
                      1024
                    ).toFixed(1)}{" "}
                    KB
                  </span>
                </div>
              </div>
            )}

            {selectedFile && (
              <button
                className="primary-button upload-button"
                onClick={
                  handleAnalyze
                }
                disabled={
                  isAnalyzing
                }
              >
                {isAnalyzing
                  ? "Analyzing..."
                  : "Analyze Document"}
              </button>
            )}

            {isAnalyzing && (
              <div className="analysis-progress">
                <div className="progress-spinner" />

                <div>
                  <strong>
                    {analysisStage ===
                    "uploading"
                      ? "Uploading document..."
                      : "Analyzing sensitive data..."}
                  </strong>

                  <span>
                    {analysisStage ===
                    "uploading"
                      ? "Preparing your document for analysis."
                      : "Running rule engine, Turkish NER and privacy decisions."}
                  </span>
                </div>
              </div>
            )}

            {error && (
              <div className="error-message">
                {error}
              </div>
            )}

            {uploadedDocument &&
              !isAnalyzing &&
              analysis && (
                <div className="success-message">
                  Analysis completed
                  successfully.
                </div>
              )}

            <div className="upload-note">
              Maximum file size: 20 MB
            </div>
          </div>

          <div className="info-panel">
            <div className="info-label">
              DETECTION ENGINE
            </div>

            <h3>
              Hybrid privacy detection
            </h3>

            <div className="detector-list">
              <div className="detector">
                <span className="detector-dot" />

                <div>
                  <strong>
                    Rule Engine
                  </strong>

                  <p>
                    Email, phone, TCKN,
                    IBAN and card numbers
                  </p>
                </div>
              </div>

              <div className="detector">
                <span className="detector-dot" />

                <div>
                  <strong>
                    Turkish NER
                  </strong>

                  <p>
                    People, locations and
                    organizations
                  </p>
                </div>
              </div>

              <div className="detector">
                <span className="detector-dot" />

                <div>
                  <strong>
                    Decision Layer
                  </strong>

                  <p>
                    Auto-redact or send
                    uncertain findings
                    for review
                  </p>
                </div>
              </div>
            </div>

            <div className="privacy-box">
              <span>
                ✓
              </span>

              <p>
                Documents are prepared
                for privacy-aware review
                before redaction.
              </p>
            </div>
          </div>
        </section>

        {analysis && (
          <section className="results-section">
            <div className="results-header">
              <div>
                <div className="eyebrow">
                  ANALYSIS RESULTS
                </div>

                <h2>
                  {
                    analysis.finding_count
                  }{" "}
                  findings detected
                </h2>
              </div>

              <div className="page-count">
                {
                  analysis.page_count
                }{" "}
                page
              </div>
            </div>

            <div className="analysis-summary">
              <div className="summary-item">
                <span>
                  Total Findings
                </span>

                <strong>
                  {
                    analysis.finding_count
                  }
                </strong>
              </div>

              <div className="summary-item auto-summary">
                <span>
                  Auto Redact
                </span>

                <strong>
                  {autoRedactCount}
                </strong>
              </div>

              <div className="summary-item review-summary">
                <span>
                  Needs Review
                </span>

                <strong>
                  {reviewCount}
                </strong>
              </div>

              <div className="summary-item">
                <span>
                  Review Selected
                </span>

                <strong>
                  {selectedReviewCount}
                </strong>
              </div>
            </div>

            {reviewCount > 0 && (
              <div className="review-toolbar">
                <div>
                  <strong>
                    Review uncertain
                    findings
                  </strong>

                  <span>
                    Select additional
                    data that should be
                    removed from the
                    document.
                  </span>
                </div>

                <div className="review-toolbar-actions">
                  <button
                    className="secondary-button"
                    onClick={
                      handleSelectAllReview
                    }
                    disabled={
                      selectedReviewCount ===
                      reviewCount
                    }
                  >
                    Select All Review
                  </button>

                  <button
                    className="secondary-button"
                    onClick={
                      handleClearReview
                    }
                    disabled={
                      selectedReviewIds.length ===
                      0
                    }
                  >
                    Clear Selection
                  </button>
                </div>
              </div>
            )}

            <div className="findings-grid">
              {analysis.findings.map(
                (
                  finding,
                  index
                ) => (
                  <div
                    className="finding-card"
                    key={
                      finding.finding_id ||
                      `${finding.type}-${finding.start}-${index}`
                    }
                  >
                    <div className="finding-top">
                      <span className="finding-type">
                        {
                          finding.type
                        }
                      </span>

                      <span
                        className={`action-badge ${
                          finding.redaction_action ===
                          "AUTO_REDACT"
                            ? "auto"
                            : "review"
                        }`}
                      >
                        {
                          finding.redaction_action
                        }
                      </span>
                    </div>

                    <div className="finding-value">
                      {
                        finding.value
                      }
                    </div>

                    {finding.redaction_action ===
                      "REVIEW" && (
                      <label className="review-control">
                        <input
                          type="checkbox"
                          checked={selectedReviewIds.includes(
                            finding.finding_id
                          )}
                          onChange={() =>
                            handleReviewToggle(
                              finding.finding_id
                            )
                          }
                        />

                        <span>
                          Include in
                          redaction
                        </span>
                      </label>
                    )}

                    {finding.redaction_action ===
                      "AUTO_REDACT" && (
                      <div className="auto-control">
                        ✓ Included
                        automatically
                      </div>
                    )}

                    <div className="finding-meta">
                      <div>
                        <span>
                          Confidence
                        </span>

                        <strong>
                          {formatConfidence(
                            finding.confidence
                          )}
                        </strong>
                      </div>

                      <div>
                        <span>
                          Level
                        </span>

                        <strong>
                          {
                            finding.confidence_level
                          }
                        </strong>
                      </div>

                      <div>
                        <span>
                          Privacy
                        </span>

                        <strong>
                          {
                            finding.privacy_status
                          }
                        </strong>
                      </div>

                      <div>
                        <span>
                          Source
                        </span>

                        <strong>
                          {
                            finding.source
                          }
                        </strong>
                      </div>
                    </div>
                  </div>
                )
              )}
            </div>

            <div className="redaction-actions">
              <div>
                <strong>
                  Ready to create
                  protected document
                </strong>

                <p>
                  Automatic findings
                  will always be
                  redacted. Review
                  findings are included
                  only when selected.
                </p>
              </div>

              <button
                className="primary-button"
                onClick={
                  handleCreateRedactedPdf
                }
                disabled={
                  isRedacting
                }
              >
                {isRedacting
                  ? "Creating PDF..."
                  : "Create Redacted PDF"}
              </button>
            </div>

            {redactionSuccess && (
              <div className="redaction-success">
                <div className="success-icon">
                  ✓
                </div>

                <div>
                  <strong>
                    Protected PDF
                    created successfully
                  </strong>

                  <span>
                    Your redacted
                    document has been
                    downloaded.
                  </span>
                </div>

                <button
                  className="secondary-button"
                  onClick={
                    handleAnalyzeAnother
                  }
                >
                  Analyze Another
                  Document
                </button>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;