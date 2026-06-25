const form = document.querySelector("#policyForm");
const writerModeInputs = [...document.querySelectorAll('input[name="writerMode"]')];
const accessGate = document.querySelector("#accessGate");
const accessModeLoginButton = document.querySelector("#accessModeLoginButton");
const accessModeSignupButton = document.querySelector("#accessModeSignupButton");
const accessModeResetButton = document.querySelector("#accessModeResetButton");
const accessLoginForm = document.querySelector("#accessLoginForm");
const accessSignupForm = document.querySelector("#accessSignupForm");
const accessResetForm = document.querySelector("#accessResetForm");
const loginEmployeeIdInput = document.querySelector("#loginEmployeeIdInput");
const loginPasswordInput = document.querySelector("#loginPasswordInput");
const accessLoginButton = document.querySelector("#accessLoginButton");
const signupNameInput = document.querySelector("#signupNameInput");
const signupEmployeeIdInput = document.querySelector("#signupEmployeeIdInput");
const signupPasswordInput = document.querySelector("#signupPasswordInput");
const signupPasswordConfirmInput = document.querySelector("#signupPasswordConfirmInput");
const signupEntryCodeInput = document.querySelector("#signupEntryCodeInput");
const accessSignupButton = document.querySelector("#accessSignupButton");
const resetEmployeeIdInput = document.querySelector("#resetEmployeeIdInput");
const resetPasswordInput = document.querySelector("#resetPasswordInput");
const resetPasswordConfirmInput = document.querySelector("#resetPasswordConfirmInput");
const resetEntryCodeInput = document.querySelector("#resetEntryCodeInput");
const accessResetButton = document.querySelector("#accessResetButton");
const accessGateMessage = document.querySelector("#accessGateMessage");
const signedInUserBadge = document.querySelector("#signedInUserBadge");
const signedInUserName = document.querySelector("#signedInUserName");
const accessLogoutButton = document.querySelector("#accessLogoutButton");
const message = document.querySelector("#message");
const submitButton = document.querySelector("#submitButton");
const requestQuickSubmitButton = document.querySelector("#requestQuickSubmitButton");
const refreshButton = document.querySelector("#refreshButton");
const serviceHealthButton = document.querySelector("#serviceHealthButton");
const userManagementButton = document.querySelector("#userManagementButton");
const piCheckButton = document.querySelector("#piCheckButton");
const channelPiStatusButton = document.querySelector("#channelPiStatusButton");
const writerModePanel = document.querySelector(".welcome-llm-choice-panel");
const documentQaReviewButton = document.querySelector("#documentQaReviewButton");
const healthCheckButton = document.querySelector("#healthCheckButton");
const alignmentCheckButton = document.querySelector("#alignmentCheckButton");
const devFormatExportButton = document.querySelector("#devFormatExportButton");
const documentAnalysisButton = document.querySelector("#documentAnalysisButton");
const policyWorkspaceActionButtons = [
  documentQaReviewButton,
  healthCheckButton,
  alignmentCheckButton,
  documentAnalysisButton,
  refreshButton,
].filter(Boolean);
const brandHomeButton = document.querySelector("#brandHomeButton");
const welcomeArea = document.querySelector("#welcomeArea");
const channelPiArea = document.querySelector("#channelPiArea");
const requestArea = document.querySelector("#requestArea");
const resultArea = document.querySelector("#resultArea");
const workspaceTitleActions = document.querySelector(".workspace-title-actions");
const appShell = document.querySelector(".app-shell");
const sideNavToggle = document.querySelector("#sideNavToggle");
const resultsLayout = document.querySelector(".results-layout");
const topicSelect = document.querySelector("#topic");
const fullTemplateTypeInput = form?.querySelector('input[name="templateType"][value="full"]');
const simpleTemplateTypeInput = form?.querySelector('input[name="templateType"][value="simple"]');
const requestTopicSummary = document.querySelector("#requestTopicSummary");
const requestTopicName = document.querySelector("#requestTopicName");
const briefInput = document.querySelector("#brief");
const workspaceTopicDirection = document.querySelector("#workspaceTopicDirection");
const topicConceptModal = document.querySelector("#topicConceptModal");
const topicConceptCloseButton = document.querySelector("#topicConceptCloseButton");
const topicConceptTitle = document.querySelector("#topicConceptTitle");
const topicConceptSummary = document.querySelector("#topicConceptSummary");
const topicConceptBody = document.querySelector("#topicConceptBody");
const topicSearch = document.querySelector("#topicSearch");
const topicChips = document.querySelector("#topicChips");
const policyTopicList = document.querySelector("#policyTopicList");
const topicStatusSearch = document.querySelector("#topicStatusSearch");
const resultList = document.querySelector("#resultList");
const previewFrame = document.querySelector("#previewFrame");
const previewTitle = document.querySelector("#previewTitle");
const previewMeta = document.querySelector("#previewMeta");
const previewTemplateBadge = document.querySelector("#previewTemplateBadge");
const previewTemplateHint = document.querySelector("#previewTemplateHint");
const versionSelectWrap = document.querySelector("#versionSelectWrap");
const versionSelect = document.querySelector("#versionSelect");
const versionChangeToggle = document.querySelector("#versionChangeToggle");
const versionChangeSummary = document.querySelector("#versionChangeSummary");
const previewMoreActions = document.querySelector("#previewMoreActions");
const openLink = document.querySelector("#openLink");
const downloadLink = document.querySelector("#downloadLink");
const jsonDownloadLink = document.querySelector("#jsonDownloadLink");
const uploadHtmlButton = document.querySelector("#uploadHtmlButton");
const uploadHtmlInput = document.querySelector("#uploadHtmlInput");
const uploadJsonButton = document.querySelector("#uploadJsonButton");
const uploadJsonInput = document.querySelector("#uploadJsonInput");
const resumeDraftButton = document.querySelector("#resumeDraftButton");
const rewritePolicyButton = document.querySelector("#rewritePolicyButton");
const fullVersionButton = document.querySelector("#fullVersionButton");
const deleteSelectedButton = document.querySelector("#deleteSelectedButton");
const completionStatusButton = document.querySelector("#completionStatusButton");
const widePreviewButton = document.querySelector("#widePreviewButton");
const editButton = document.querySelector("#editButton");
const saveEditButton = document.querySelector("#saveEditButton");
const cancelEditButton = document.querySelector("#cancelEditButton");
const editorModeChip = document.querySelector("#editorModeChip");
const editorToolbar = document.querySelector("#editorToolbar");
const editorToolButtons = [...document.querySelectorAll("[data-editor-command]")];
const editorTableActionButtons = editorToolButtons.filter((button) => button.dataset.tableAction === "true");
const editorFontSizeSelect = document.querySelector("#editorFontSizeSelect");
const editorBulletStyleSelect = document.querySelector("#editorBulletStyleSelect");
const diagramEditorModal = document.querySelector("#diagramEditorModal");
const diagramEditorCloseButton = document.querySelector("#diagramEditorCloseButton");
const diagramEditorCancelButton = document.querySelector("#diagramEditorCancelButton");
const diagramEditorSaveButton = document.querySelector("#diagramEditorSaveButton");
const diagramEditorSummary = document.querySelector("#diagramEditorSummary");
const diagramEditorStatus = document.querySelector("#diagramEditorStatus");
const diagramEditorSaveMode = document.querySelector("#diagramEditorSaveMode");
const diagramEditorTabs = [...document.querySelectorAll("[data-diagram-tab]")];
const diagramEditorPanes = [...document.querySelectorAll("[data-diagram-pane]")];
const diagramActorsInput = document.querySelector("#diagramActorsInput");
const diagramUsecasesInput = document.querySelector("#diagramUsecasesInput");
const diagramStatesInput = document.querySelector("#diagramStatesInput");
const diagramTransitionsInput = document.querySelector("#diagramTransitionsInput");
const diagramProcessesInput = document.querySelector("#diagramProcessesInput");
const revisionPanel = document.querySelector("#revisionPanel");
const revisionRequest = document.querySelector("#revisionRequest");
const revisionButton = document.querySelector("#revisionButton");
const selectionRevisionButton = document.querySelector("#selectionRevisionButton");
if (selectionRevisionButton && selectionRevisionButton.parentElement !== document.body) {
  document.body.appendChild(selectionRevisionButton);
}
const selectionInlineRequest = document.querySelector("#selectionInlineRequest");
const selectionInlineAiButton = document.querySelector("#selectionInlineAiButton");
const selectionInlineCommentButton = document.querySelector("#selectionInlineCommentButton");
const selectionRevisionModal = document.querySelector("#selectionRevisionModal");
const selectionRevisionCloseButton = document.querySelector("#selectionRevisionCloseButton");
const selectionRevisionCancelButton = document.querySelector("#selectionRevisionCancelButton");
const selectionRevisionSubmitButton = document.querySelector("#selectionRevisionSubmitButton");
const selectionRevisionRequest = document.querySelector("#selectionRevisionRequest");
const selectionRevisionExcerpt = document.querySelector("#selectionRevisionExcerpt");
const selectionRevisionSection = document.querySelector("#selectionRevisionSection");
const selectionRevisionModeInputs = [...document.querySelectorAll('input[name="selectionRevisionMode"]')];
const widePreviewModal = document.querySelector("#widePreviewModal");
const widePreviewCloseButton = document.querySelector("#widePreviewCloseButton");
const widePreviewFrame = document.querySelector("#widePreviewFrame");
const widePreviewSummary = document.querySelector("#widePreviewSummary");
const editSaveModeModal = document.querySelector("#editSaveModeModal");
const editSaveModeTitle = document.querySelector("#editSaveModeTitle");
const editSaveModeSubcopy = editSaveModeModal?.querySelector(".edit-save-mode-subcopy");
const editSaveModeCloseButton = document.querySelector("#editSaveModeCloseButton");
const editSaveModeCancelButton = document.querySelector("#editSaveModeCancelButton");
const editSaveModeNewVersionButton = document.querySelector("#editSaveModeNewVersionButton");
const editSaveModeOverwriteButton = document.querySelector("#editSaveModeOverwriteButton");
const editChangeReview = document.querySelector("#editChangeReview");
const editReviewSummary = document.querySelector("#editReviewSummary");
const editReviewFindings = document.querySelector("#editReviewFindings");
const fullVersionModal = document.querySelector("#fullVersionModal");
const fullVersionCloseButton = document.querySelector("#fullVersionCloseButton");
const fullVersionCancelButton = document.querySelector("#fullVersionCancelButton");
const fullVersionStartButton = document.querySelector("#fullVersionStartButton");
const documentQaReviewModal = document.querySelector("#documentQaReviewModal");
const documentQaReviewStartButton = document.querySelector("#documentQaReviewStartButton");
const documentQaActionCheckButton = document.querySelector("#documentQaActionCheckButton");
const documentQaReviewCloseButton = document.querySelector("#documentQaReviewCloseButton");
const documentQaReviewSummary = document.querySelector("#documentQaReviewSummary");
const documentQaStatus = document.querySelector("#documentQaStatus");
const documentQaLoadingPanel = document.querySelector("#documentQaLoadingPanel");
const documentQaLoadingPercent = document.querySelector("#documentQaLoadingPercent");
const documentQaLoadingBar = document.querySelector("#documentQaLoadingBar");
const documentQaLoadingPolicy = document.querySelector("#documentQaLoadingPolicy");
const documentQaLoadingElapsed = document.querySelector("#documentQaLoadingElapsed");
const documentQaLoadingCurrent = document.querySelector("#documentQaLoadingCurrent");
const documentQaLoadingSteps = document.querySelector("#documentQaLoadingSteps");
const documentQaResultStats = document.querySelector("#documentQaResultStats");
const documentQaResultSection = document.querySelector("#documentQaResultSection");
const documentQaResultCount = document.querySelector("#documentQaResultCount");
const documentQaResultList = document.querySelector("#documentQaResultList");
const devFindingCount = document.querySelector("#devFindingCount");
const devFindingList = document.querySelector("#devFindingList");
const qaFindingCount = document.querySelector("#qaFindingCount");
const qaFindingList = document.querySelector("#qaFindingList");
const qaCoverageList = document.querySelector("#qaCoverageList");
const qaActionCount = document.querySelector("#qaActionCount");
const qaActionList = document.querySelector("#qaActionList");
const qaGapCount = document.querySelector("#qaGapCount");
const qaGapList = document.querySelector("#qaGapList");
const documentQaSelectionSummary = document.querySelector("#documentQaSelectionSummary");
const documentQaRevisionButton = document.querySelector("#documentQaRevisionButton");
const documentQaFooter = document.querySelector(".document-qa-footer");
const healthCheckModal = document.querySelector("#healthCheckModal");
const healthCheckStartButton = document.querySelector("#healthCheckStartButton");
const healthCheckCloseButton = document.querySelector("#healthCheckCloseButton");
const healthCheckSummary = document.querySelector("#healthCheckSummary");
const healthCheckStatus = document.querySelector("#healthCheckStatus");
const healthCheckStats = document.querySelector("#healthCheckStats");
const healthCheckSectionCount = document.querySelector("#healthCheckSectionCount");
const healthCheckSectionChart = document.querySelector("#healthCheckSectionChart");
const healthCheckSectionList = document.querySelector("#healthCheckSectionList");
const healthCheckGateCount = document.querySelector("#healthCheckGateCount");
const healthCheckGateList = document.querySelector("#healthCheckGateList");
const healthCheckItemCount = document.querySelector("#healthCheckItemCount");
const healthCheckItemList = document.querySelector("#healthCheckItemList");
const healthCheckSelectionSummary = document.querySelector("#healthCheckSelectionSummary");
const healthCheckRevisionButton = document.querySelector("#healthCheckRevisionButton");
const healthCheckRecheckButton = document.querySelector("#healthCheckRecheckButton");
const healthCheckExportButton = document.querySelector("#healthCheckExportButton");
const healthCheckArtifactRepairButton = document.querySelector("#healthCheckArtifactRepairButton");
const healthCheckFooter = document.querySelector(".health-check-footer");
const devFormatExportModal = document.querySelector("#devFormatExportModal");
const devFormatExportStartButton = document.querySelector("#devFormatExportStartButton");
const devFormatExportCloseButton = document.querySelector("#devFormatExportCloseButton");
const devFormatExportSummary = document.querySelector("#devFormatExportSummary");
const devFormatExportStatus = document.querySelector("#devFormatExportStatus");
const devFormatExportStats = document.querySelector("#devFormatExportStats");
const devFormatExportArtifactCount = document.querySelector("#devFormatExportArtifactCount");
const devFormatExportArtifactList = document.querySelector("#devFormatExportArtifactList");
const devFormatExportWarningCount = document.querySelector("#devFormatExportWarningCount");
const devFormatExportWarningList = document.querySelector("#devFormatExportWarningList");
const devFormatExportDiagramNoteSection = document.querySelector("#devFormatExportDiagramNoteSection");
const devFormatExportDiagramNoteCount = document.querySelector("#devFormatExportDiagramNoteCount");
const devFormatExportDiagramNoteList = document.querySelector("#devFormatExportDiagramNoteList");
const devFormatExportFooter = document.querySelector(".dev-format-export-footer");
const devFormatExportFooterSummary = document.querySelector("#devFormatExportFooterSummary");
const devFormatExportZipLink = document.querySelector("#devFormatExportZipLink");
const alignmentCheckModal = document.querySelector("#alignmentCheckModal");
const alignmentCheckStartButton = document.querySelector("#alignmentCheckStartButton");
const alignmentCheckCloseButton = document.querySelector("#alignmentCheckCloseButton");
const alignmentCheckSummary = document.querySelector("#alignmentCheckSummary");
const alignmentCheckStatus = document.querySelector("#alignmentCheckStatus");
const alignmentCheckStats = document.querySelector("#alignmentCheckStats");
const alignmentCheckSourceCount = document.querySelector("#alignmentCheckSourceCount");
const alignmentCheckSourceList = document.querySelector("#alignmentCheckSourceList");
const alignmentCheckAnalysisCount = document.querySelector("#alignmentCheckAnalysisCount");
const alignmentCheckAnalysisList = document.querySelector("#alignmentCheckAnalysisList");
const alignmentCheckPolicyCount = document.querySelector("#alignmentCheckPolicyCount");
const alignmentCheckPolicyList = document.querySelector("#alignmentCheckPolicyList");
const alignmentCheckActionCount = document.querySelector("#alignmentCheckActionCount");
const alignmentCheckActionList = document.querySelector("#alignmentCheckActionList");
const channelPiHomeButton = document.querySelector("#channelPiHomeButton");
const channelPiDiagnoseButton = document.querySelector("#channelPiDiagnoseButton");
const channelPiSummary = document.querySelector("#channelPiSummary");
const channelPiStatusCard = document.querySelector("#channelPiStatusCard");
const channelPiProgress = document.querySelector("#channelPiProgress");
const channelPiProgressLabel = document.querySelector("#channelPiProgressLabel");
const channelPiProgressTitle = document.querySelector("#channelPiProgressTitle");
const channelPiProgressPercent = document.querySelector("#channelPiProgressPercent");
const channelPiProgressBar = document.querySelector("#channelPiProgressBar");
const channelPiProgressSteps = document.querySelector("#channelPiProgressSteps");
const channelPiStageFlow = document.querySelector("#channelPiStageFlow");
const channelPiStats = document.querySelector("#channelPiStats");
const channelPiDimensionCount = document.querySelector("#channelPiDimensionCount");
const channelPiDimensionList = document.querySelector("#channelPiDimensionList");
const channelPiSourceCount = document.querySelector("#channelPiSourceCount");
const channelPiSourceList = document.querySelector("#channelPiSourceList");
const channelPiAnalysisItemCount = document.querySelector("#channelPiAnalysisItemCount");
const channelPiAnalysisItemList = document.querySelector("#channelPiAnalysisItemList");
const channelPiCrossCount = document.querySelector("#channelPiCrossCount");
const channelPiCrossSummary = document.querySelector("#channelPiCrossSummary");
const channelPiCrossList = document.querySelector("#channelPiCrossList");
const channelPiTopicCount = document.querySelector("#channelPiTopicCount");
const channelPiTopicTableBody = document.querySelector("#channelPiTopicTableBody");
const channelPiActionCount = document.querySelector("#channelPiActionCount");
const channelPiActionList = document.querySelector("#channelPiActionList");
const piCheckModal = document.querySelector("#piCheckModal");
const piCheckStartButton = document.querySelector("#piCheckStartButton");
const piCheckCloseButton = document.querySelector("#piCheckCloseButton");
const piCheckAsIsFileInput = document.querySelector("#piCheckAsIsFileInput");
const piCheckAsIsFileLabel = document.querySelector("#piCheckAsIsFileLabel");
const piCheckToBeFileInput = document.querySelector("#piCheckToBeFileInput");
const piCheckToBeFileLabel = document.querySelector("#piCheckToBeFileLabel");
const piCheckSummary = document.querySelector("#piCheckSummary");
const piCheckProgress = document.querySelector("#piCheckProgress");
const piCheckProgressLabel = document.querySelector("#piCheckProgressLabel");
const piCheckProgressValue = document.querySelector("#piCheckProgressValue");
const piCheckProgressBar = document.querySelector("#piCheckProgressBar");
const piCheckProgressDetail = document.querySelector("#piCheckProgressDetail");
const piCheckStatus = document.querySelector("#piCheckStatus");
const piCheckStats = document.querySelector("#piCheckStats");
const piCheckComparisonSection = document.querySelector("#piCheckComparisonSection");
const piCheckComparisonBadge = document.querySelector("#piCheckComparisonBadge");
const piCheckComparisonList = document.querySelector("#piCheckComparisonList");
const piCheckItemCount = document.querySelector("#piCheckItemCount");
const piCheckItemList = document.querySelector("#piCheckItemList");
const piCheckAntiPatternCount = document.querySelector("#piCheckAntiPatternCount");
const piCheckAntiPatternList = document.querySelector("#piCheckAntiPatternList");
const piCheckRecommendationCount = document.querySelector("#piCheckRecommendationCount");
const piCheckRecommendationList = document.querySelector("#piCheckRecommendationList");
const piCheckFooter = document.querySelector(".pi-check-footer");
const piCheckFooterSummary = document.querySelector("#piCheckFooterSummary");
const piCheckExportButton = document.querySelector("#piCheckExportButton");
const documentAnalysisModal = document.querySelector("#documentAnalysisModal");
const documentAnalysisCloseButton = document.querySelector("#documentAnalysisCloseButton");
const documentAnalysisSummary = document.querySelector("#documentAnalysisSummary");
const documentAnalysisGrid = document.querySelector("#documentAnalysisGrid");
const documentHealthGrid = document.querySelector("#documentHealthGrid");
const serviceHealthModal = document.querySelector("#serviceHealthModal");
const serviceHealthCloseButton = document.querySelector("#serviceHealthCloseButton");
const serviceHealthRefreshButton = document.querySelector("#serviceHealthRefreshButton");
const serviceLockCleanupButton = document.querySelector("#serviceLockCleanupButton");
const serviceHealthSummary = document.querySelector("#serviceHealthSummary");
const serviceHealthStats = document.querySelector("#serviceHealthStats");
const serviceRecommendationCount = document.querySelector("#serviceRecommendationCount");
const serviceRecommendationList = document.querySelector("#serviceRecommendationList");
const serviceDiskCount = document.querySelector("#serviceDiskCount");
const serviceDiskList = document.querySelector("#serviceDiskList");
const serviceLockCount = document.querySelector("#serviceLockCount");
const serviceLockList = document.querySelector("#serviceLockList");
const serviceQueueCount = document.querySelector("#serviceQueueCount");
const serviceQueueList = document.querySelector("#serviceQueueList");
const serviceRuntimeCount = document.querySelector("#serviceRuntimeCount");
const serviceRuntimeList = document.querySelector("#serviceRuntimeList");
const serviceUsageCount = document.querySelector("#serviceUsageCount");
const serviceUsageList = document.querySelector("#serviceUsageList");
const userManagementModal = document.querySelector("#userManagementModal");
const userManagementCloseButton = document.querySelector("#userManagementCloseButton");
const userManagementRefreshButton = document.querySelector("#userManagementRefreshButton");
const userManagementSummary = document.querySelector("#userManagementSummary");
const userManagementStats = document.querySelector("#userManagementStats");
const userManagementCount = document.querySelector("#userManagementCount");
const userManagementList = document.querySelector("#userManagementList");
const policyCount = document.querySelector("#policyCount");
const llmStatus = document.querySelector("#llmStatus");
const progressModal = document.querySelector("#progressModal");
const progressTitle = document.querySelector("#progressTitle");
const progressCloseButton = document.querySelector("#progressCloseButton");
const progressCancelButton = document.querySelector("#progressCancelButton");
const progressPolicyTarget = document.querySelector("#progressPolicyTarget");
const progressMessage = document.querySelector("#progressMessage");
const totalElapsed = document.querySelector("#totalElapsed");
const currentStageElapsed = document.querySelector("#currentStageElapsed");
const currentStageName = document.querySelector("#currentStageName");
const jobStatus = document.querySelector("#jobStatus");
const progressSteps = document.querySelector("#progressSteps");
const progressStepCount = document.querySelector("#progressStepCount");
const progressError = document.querySelector("#progressError");
const progressActivityTitle = document.querySelector("#progressActivityTitle");
const progressActivityMeta = document.querySelector("#progressActivityMeta");
const progressActivityMessage = document.querySelector("#progressActivityMessage");
const progressArtifactList = document.querySelector("#progressArtifactList");
const progressFocusDescription = document.querySelector("#progressFocusDescription");
const progressOverallPercent = document.querySelector("#progressOverallPercent");
const progressOverallBar = document.querySelector("#progressOverallBar");
const progressEta = document.querySelector("#progressEta");
const progressGate = document.querySelector("#progressGate");
const progressCurrentWorkList = document.querySelector("#progressCurrentWorkList");
const progressGateList = document.querySelector("#progressGateList");
const progressNextList = document.querySelector("#progressNextList");
const progressLifeFeedbackList = document.querySelector("#progressLifeFeedbackList");
const progressLifeFeedbackTone = document.querySelector("#progressLifeFeedbackTone");
const progressManualReviewArea = document.querySelector("#progressManualReviewArea");
const progressFocusCards = document.querySelector("#progressFocusCards");
const progressInspectorCount = document.querySelector("#progressInspectorCount");
const progressInspectorNotes = document.querySelector("#progressInspectorNotes");
const manualReviewPanel = document.querySelector("#manualReviewPanel");
const manualReviewTitle = document.querySelector("#manualReviewTitle");
const manualReviewMessage = document.querySelector("#manualReviewMessage");
const manualReviewArtifact = document.querySelector("#manualReviewArtifact");
const manualReviewInstruction = document.querySelector("#manualReviewInstruction");
const manualReviewInstructionField = manualReviewInstruction?.closest(".field");
const manualReviewInstructionLabel = manualReviewInstructionField?.querySelector("span");
const manualContinueButton = document.querySelector("#manualContinueButton");
const manualReviseButton = document.querySelector("#manualReviseButton");
const dashboardTotalPolicies = document.querySelector("#dashboardTotalPolicies");
const dashboardDraftPolicies = document.querySelector("#dashboardDraftPolicies");
const dashboardCompletedPolicies = document.querySelector("#dashboardCompletedPolicies");
const dashboardTodoPolicies = document.querySelector("#dashboardTodoPolicies");
const agentDashboardRows = document.querySelector("#agentDashboardRows");
const agentDashboardMeta = document.querySelector("#agentDashboardMeta");
const agentTotalCalls = document.querySelector("#agentTotalCalls");
const agentTotalTokens = document.querySelector("#agentTotalTokens");
const agentTotalCost = document.querySelector("#agentTotalCost");
const agentDiskUsage = document.querySelector("#agentDiskUsage");
const workspaceAssistPanel = document.querySelector("#workspaceAssistPanel");
const workspaceAssistModeInputs = [...document.querySelectorAll('input[name="workspaceAssistMode"]')];
const workspaceAssistTabButtons = [...document.querySelectorAll("[data-assist-tab]")];
const workspaceAssistPanes = [...document.querySelectorAll("[data-assist-pane]")];
const commentWorkspaceTools = document.querySelector("#commentWorkspaceTools");
const aiCommentList = document.querySelector("#aiCommentList");
const aiCommentCount = document.querySelector("#aiCommentCount");
const selectedElementList = document.querySelector("#selectedElementList");
const selectedElementCount = document.querySelector("#selectedElementCount");
const editorSuggestionList = document.querySelector("#editorSuggestionList");
const editorSuggestionCount = document.querySelector("#editorSuggestionCount");
const editorCommentList = document.querySelector("#editorCommentList");
const editorCommentCount = document.querySelector("#editorCommentCount");
const editorCommentSearchInput = document.querySelector("#editorCommentSearchInput");
const editorCommentStatusFilterInputs = [...document.querySelectorAll("[data-comment-status-filter]")];
const editorCommentFilterLabel = document.querySelector("#editorCommentFilterLabel");
const editorCommentFilterMenu = document.querySelector("#editorCommentFilterMenu");
const editorCommentSortButtons = [...document.querySelectorAll("[data-comment-sort]")];
const editorCommentSortLabel = document.querySelector("#editorCommentSortLabel");
const editorCommentSortMenu = document.querySelector("#editorCommentSortMenu");
const editorCommentStickyPanel = document.querySelector("#editorCommentStickyPanel");
const editorCommentComposerSlot = document.querySelector("#editorCommentComposerSlot");
const editorCommentComposer = document.querySelector("#editorCommentComposer");
const editorCommentTarget = document.querySelector("#editorCommentTarget");
const editorCommentInput = document.querySelector("#editorCommentInput");
const editorCommentSubmitButton = document.querySelector("#editorCommentSubmitButton");
const policyValueList = document.querySelector("#policyValueList");
const policyValueCount = document.querySelector("#policyValueCount");
const tbdList = document.querySelector("#tbdList");
const tbdCount = document.querySelector("#tbdCount");
const historyList = document.querySelector("#historyList");
const historyCount = document.querySelector("#historyCount");
const API_ORIGIN = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";
const CLIENT_SESSION_ID = resolveClientSessionId();
const JOB_HEARTBEAT_INTERVAL_MS = 15000;
const HTML_UPLOAD_MAX_BYTES = 10 * 1024 * 1024;
const JSON_UPLOAD_MAX_BYTES = 10 * 1024 * 1024;
const PI_CHECK_MAX_BYTES = 20 * 1024 * 1024;
const CHANNEL_PI_EXCLUDED_SOURCE_GROUPS = new Set(["VoC 분석 종합"]);
const CHANNEL_PI_PROGRESS_STEPS = [
  {
    label: "현황 분석",
    title: "현황 분석 근거 수집",
    description: "벤치마킹, 고객 조사, 인터뷰, IA, VoC 분석 항목을 읽고 있습니다.",
  },
  {
    label: "과제 정의",
    title: "전략 과제 연결 확인",
    description: "12개 과제 정의가 분석 근거와 요구사항으로 이어지는지 확인합니다.",
  },
  {
    label: "요구사항",
    title: "요구사항 Trace 계산",
    description: "상세 요구사항과 정책서 반영 위치를 매칭합니다.",
  },
  {
    label: "정책서",
    title: "정책서 반영도 산출",
    description: "34개 정책서의 유즈케이스, 프로세스, 기능, 정책 근거를 비교합니다.",
  },
  {
    label: "교차검증",
    title: "양방향 교차검증",
    description: "분석에서 정책으로, 정책에서 분석으로 추적이 맞는지 재확인합니다.",
  },
  {
    label: "종합",
    title: "종합 점수 생성",
    description: "진단 축별 점수와 우선 보강 액션을 정리합니다.",
  },
];
const NEXT_CHANNEL_TREE_STORAGE_KEY = "nova.nextChannelTreeOpen";
const NEXT_CHANNEL_ANALYSIS_TREE_STORAGE_KEY = "nova.nextChannelAnalysisTreeOpen";
const NEXT_CHANNEL_FUNCTION_INVENTORY_TREE_STORAGE_KEY = "nova.nextChannelFunctionInventoryTreeOpen";
const NEXT_CHANNEL_VOC_ANALYSIS_TREE_STORAGE_KEY = "nova.nextChannelVocAnalysisTreeOpen";
const NEXT_CHANNEL_TASK_DEFINITION_TREE_STORAGE_KEY = "nova.nextChannelTaskDefinitionTreeOpen";
const NEXT_CHANNEL_REQUIREMENTS_TREE_STORAGE_KEY = "nova.nextChannelRequirementsTreeOpen";
const NEXT_CHANNEL_POLICY_TREE_STORAGE_KEY = "nova.nextChannelPolicyTreeOpen";
const NEXT_BSS_TREE_STORAGE_KEY = "nova.nextBssTreeOpen";
const TOPIC_TREE_COLLAPSED_DEFAULT_APPLIED_KEY = "nova.topicTreeCollapsedDefaultApplied.v1";
const SIDE_NAV_COLLAPSED_STORAGE_KEY = "nova.sideNavCollapsed";
const SIDE_NAV_COLLAPSED_DEFAULT_APPLIED_KEY = "nova.sideNavCollapsedDefaultApplied.v1";
const WORKSPACE_ASSIST_ENABLED_STORAGE_KEY = "nova.workspaceAssistEnabled";
const COMPACT_WORKSPACE_QUERY = "(max-width: 1280px)";
const EDITOR_COMMENT_STORAGE_PREFIX = "nova.editorComments";
const EDITOR_COMMENT_MIGRATION_PREFIX = "nova.editorCommentsMigrated";
const EDITOR_SUGGESTION_STORAGE_PREFIX = "nova.editorSuggestions";
const EDITOR_COMMENT_STATUSES = ["Open", "반영됨", "보류"];
const PREVIEW_COMMENT_HIGHLIGHT_CLASS = "nc-preview-comment-highlight";
const PREVIEW_COMMENT_ANCHOR_CLASS = "nc-preview-comment-anchor";
const PREVIEW_COMMENT_MARKER_CLASS = "nc-preview-comment-marker";
const PREVIEW_COMMENT_SELECTED_CLASS = "nc-preview-comment-selected";
const VERSION_CHANGE_HIGHLIGHT_CLASS = "nc-preview-version-change-highlight";
const VERSION_CHANGE_ACTIVE_CLASS = "nc-preview-version-change-active";
const VERSION_CHANGE_BADGE_CLASS = "nc-preview-version-change-badge";
const VERSION_CHANGE_COLLECTIONS = [
  { key: "usecases", label: "유즈케이스", idKeys: ["id"], titleKeys: ["name"] },
  { key: "state_codes", label: "상태", idKeys: ["id", "code"], titleKeys: ["name"] },
  { key: "state_transitions", label: "상태 전이", idKeys: ["id"], titleKeys: ["event"], fallback: "transition" },
  { key: "processes", label: "프로세스", idKeys: ["id"], titleKeys: ["name"] },
  { key: "functions", label: "기능", idKeys: ["id"], titleKeys: ["name"] },
  { key: "policy_groups", label: "정책 그룹", idKeys: ["id"], titleKeys: ["name"] },
  { key: "policy_details", label: "정책 항목", idKeys: ["id", "item_id"], titleKeys: ["name"] },
];
const HEALTH_CHECK_PROGRESS_STEPS = [
  {
    label: "01",
    title: "문서 구조 읽기",
    description: "선택한 정책서의 장, 표, 정책 항목, trace 근거를 불러옵니다.",
  },
  {
    label: "02",
    title: "10개 품질 영역 점검",
    description: "범위, 고객 경험, 프로세스, 기능, 정책 구체성 기준을 대조합니다.",
  },
  {
    label: "03",
    title: "Gate 검증",
    description: "요구사항 커버리지, 연결성, 산출물 동기화, 평가 품질 Gate를 확인합니다.",
  },
  {
    label: "04",
    title: "보완 후보 정리",
    description: "FAIL 또는 보완 필요 항목을 우선순위와 수정 위치 기준으로 묶습니다.",
  },
  {
    label: "05",
    title: "결과 보드 생성",
    description: "영역별 점수, 필수 Gate, 자동 보완 후보를 화면에 반영합니다.",
  },
];
const HEALTH_CHECK_FALLBACK_AREAS = [
  "범위 정합성",
  "고객 완결성",
  "고객 이해 가능성",
  "BSS·연계 포함성",
  "상태 전이 정합성",
  "프로세스-기능-정책 연결성",
  "정책명 정합성",
  "정책 구체성",
  "개인정보·로그 보호",
  "운영 관리·요구사항 추적",
];
const USER_MANAGEMENT_EMPLOYEE_IDS = new Set(["1111120"]);
const VOC_ANALYSIS_REFERENCES = [
  { id: "voc-summary", title: "종합", url: "/output/reference_html/voc-summary.html" },
  { id: "voc-auto-payment-apply-change", title: "자동 납부 신청 변경", url: "/output/reference_html/voc-auto-payment-apply-change.html" },
  { id: "voc-t-universe-subscription", title: "우주 패스 / T우주 / 구독", url: "/output/reference_html/voc-t-universe-subscription.html" },
  { id: "voc-paper-bill", title: "우편 청구서", url: "/output/reference_html/voc-paper-bill.html" },
  { id: "voc-add-on-cancel", title: "부가서비스 해지", url: "/output/reference_html/voc-add-on-cancel.html" },
  { id: "voc-address-change", title: "주소 변경", url: "/output/reference_html/voc-address-change.html" },
  { id: "voc-lost-device", title: "분실", url: "/output/reference_html/voc-lost-device.html" },
  { id: "voc-bundle", title: "결합", url: "/output/reference_html/voc-bundle.html" },
  { id: "voc-bill-info", title: "청구서 정보", url: "/output/reference_html/voc-bill-info.html" },
  { id: "voc-contact-change", title: "연락처 변경", url: "/output/reference_html/voc-contact-change.html" },
  { id: "voc-membership", title: "멤버십", url: "/output/reference_html/voc-membership.html" },
  { id: "voc-temporary-suspension", title: "일시 정지", url: "/output/reference_html/voc-temporary-suspension.html" },
  { id: "voc-plan-change", title: "요금제 변경", url: "/output/reference_html/voc-plan-change.html" },
  { id: "voc-direct-shop", title: "다이렉트 샵 / 티월드 다이렉트", url: "/output/reference_html/voc-direct-shop.html" },
  { id: "voc-contract-discount", title: "약정 할인 / 선택 약정", url: "/output/reference_html/voc-contract-discount.html" },
  { id: "voc-bank-transfer-payment", title: "계좌 이체 요금 납부", url: "/output/reference_html/voc-bank-transfer-payment.html" },
  { id: "voc-auto-payment-cancel", title: "자동 납부 해지", url: "/output/reference_html/voc-auto-payment-cancel.html" },
  { id: "voc-card-payment", title: "신용 카드 요금 납부", url: "/output/reference_html/voc-card-payment.html" },
  { id: "voc-auto-payment-apply", title: "자동 납부 신청 / 자동 납부 변경", url: "/output/reference_html/voc-auto-payment-apply.html" },
  { id: "voc-add-on-join", title: "부가서비스 가입", url: "/output/reference_html/voc-add-on-join.html" },
  { id: "voc-wave-flo", title: "웨이브 / 플로", url: "/output/reference_html/voc-wave-flo.html" },
  { id: "voc-refill-coupon", title: "리필 쿠폰", url: "/output/reference_html/voc-refill-coupon.html" },
  { id: "voc-discount-change", title: "할인 변경", url: "/output/reference_html/voc-discount-change.html" },
  { id: "voc-data-gift", title: "데이터 선물", url: "/output/reference_html/voc-data-gift.html" },
  { id: "voc-mobile-cancel", title: "휴대폰 해지 / 핸드폰 해지 / 번호 해지", url: "/output/reference_html/voc-mobile-cancel.html" },
  { id: "voc-suspension-release", title: "정지 해제 / 일시 정지 해제", url: "/output/reference_html/voc-suspension-release.html" },
];
const ANALYSIS_REFERENCES = [
  { id: "ia-analysis", title: "IA 분석", url: "/output/reference_html/ia-analysis.html" },
  { id: "screen-flow", title: "화면 Flow", url: "/output/reference_html/screen-flow.html" },
  {
    id: "function-inventory",
    title: "기능 내역",
    children: [
      { id: "function-inventory-tworld", title: "T 월드", url: "/output/reference_html/function-inventory-tworld.html" },
      { id: "function-inventory-membership", title: "T 멤버십", url: "/output/reference_html/function-inventory-membership.html" },
      { id: "function-inventory-direct", title: "T 다이렉트", url: "/output/reference_html/function-inventory-direct.html" },
      { id: "function-inventory-universe", title: "T 우주", url: "/output/reference_html/function-inventory-universe.html" },
      { id: "function-inventory-biz", title: "T 월드 Biz", url: "/output/reference_html/function-inventory-biz.html" },
      { id: "function-inventory-integrated", title: "통합 기능 목록", url: "/output/reference_html/function-inventory-integrated.html" },
    ],
  },
  { id: "service-policy", title: "서비스 정책", url: "/output/reference_html/service-policy.html" },
  { id: "customer-research", title: "고객 조사", url: "/output/reference_html/customer-research.html" },
  { id: "employee-interview", title: "임직원 인터뷰", url: "/output/reference_html/employee-interview.html" },
  { id: "benchmarking", title: "벤치마킹", url: "/output/reference_html/benchmarking.html" },
  { id: "voc-analysis", title: "VoC 분석", children: VOC_ANALYSIS_REFERENCES },
];
const TASK_DEFINITION_REFERENCES = [
  { id: "tk-task-06", title: "전시 운영 및 관리 체계 고도화", url: "/output/reference_html/tk-task-06.html", pages: 6, status: "completed", statusLabel: "분석 완료" },
  { id: "tk-task-03", title: "AI 기반 상품 할인 의사결정 체계 구축", url: "/output/reference_html/tk-task-03.html", pages: 5, status: "completed", statusLabel: "분석 완료" },
  { id: "tk-task-01", title: "AI 기반 탐색·추천 및 데이터 트래킹 체계 구축", url: "/output/reference_html/tk-task-01.html", pages: 6, status: "completed", statusLabel: "분석 완료" },
  { id: "tk-task-07", title: "주문 경험 혁신 프로세스 재설계", url: "/output/reference_html/tk-task-07.html", pages: 8, status: "completed", statusLabel: "분석 완료" },
  { id: "tk-task-02", title: "결제 경험 및 처리 효율화 체계 구축", url: "/output/reference_html/tk-task-02.html", pages: 5, status: "completed", statusLabel: "분석 완료" },
  { id: "tk-task-08", title: "주문 사후 관리 체계 고도화", url: "/output/reference_html/tk-task-08.html", pages: 4, status: "completed", statusLabel: "분석 완료" },
  { id: "tk-task-04", title: "상품·서비스 자산 이용 경험 재설계", url: "/output/reference_html/tk-task-04.html", pages: 6, status: "completed", statusLabel: "분석 완료" },
  { id: "tk-task-05", title: "이벤트·멤버십·리워드 통합 관리 체계 구축", url: "/output/reference_html/tk-task-05.html", pages: 6, status: "completed", statusLabel: "분석 완료" },
  { id: "tk-task-09", title: "통합 가입정보 기반 셀프 관리 체계 구축", url: "/output/reference_html/tk-task-09.html", pages: 9, status: "completed", statusLabel: "분석 완료" },
  { id: "tk-task-10", title: "셀프 완결형 요금 납부·관리 경험 재설계", url: "/output/reference_html/tk-task-10.html", pages: 7, status: "completed", statusLabel: "분석 완료" },
  { id: "tk-task-11", title: "셀프 해결 중심 고객지원 체계 구축", url: "/output/reference_html/tk-task-11.html", pages: 7, status: "completed", statusLabel: "분석 완료" },
  { id: "tk-task-12", title: "회원 기반 계정·인증·알림·약관 관리 체계 구축", url: "/output/reference_html/tk-task-12.html", pages: 5, status: "completed", statusLabel: "분석 완료" },
];

let currentItems = [];
let currentDrafts = [];
let currentDashboard = null;
let selectedName = "";
let selectedDraft = null;
let selectedAnalysisReferenceId = "";
let selectedTaskDefinitionId = "";
let selectedRequirementTopic = "";
let activeJobId = "";
let progressTimer = null;
let progressHeartbeatTimer = null;
let isEditing = false;
let originalPreviewUrl = "";
let editingBaseHash = "";
let diagramEditorBaseHash = "";
let editingOriginalHtml = "";
let editingOriginalText = "";
let widePreviewRestoreFocusTarget = null;
let currentProgressJob = null;
let versionChangeEnabled = false;
let versionChangeLoading = false;
let versionChangeData = null;
let versionChangeRequestId = 0;
let selectedRevisionTarget = null;
let selectedEditorContext = null;
let editorComments = [];
let editorCommentSearchQuery = "";
let editorCommentStatusFilterValues = new Set(EDITOR_COMMENT_STATUSES);
let editorCommentSortOrder = "recent";
let selectedEditorCommentId = "";
let editorCommentLoadToken = 0;
let editorCommentsSyncing = false;
let editorSuggestions = [];
let latestQaReviewReport = null;
let pendingQaActionCheck = null;
let latestHealthCheckReport = null;
let latestAlignmentCheckReport = null;
let latestChannelPiStatusReport = null;
let latestPiCheckReport = null;
let latestDevFormatExport = null;
let documentQaLoadingStartedAt = 0;
let documentQaLoadingTimer = null;
let documentQaReviewInFlight = false;
let healthCheckInFlight = false;
let devFormatExportInFlight = false;
let alignmentCheckInFlight = false;
let channelPiStatusInFlight = false;
let channelPiProgressStartedAt = 0;
let channelPiProgressTimer = null;
let healthCheckRubricLoading = false;
let piCheckInFlight = false;
let piCheckRubricLoading = false;
let serviceHealthInFlight = false;
let userManagementInFlight = false;
let accessAuthorized = false;
let currentUser = null;
let activeMainWorkspace = "welcome";
applyTopicTreeCollapsedDefault();
let nextChannelTreeOpen = readStoredBoolean(NEXT_CHANNEL_TREE_STORAGE_KEY, false);
let nextChannelAnalysisTreeOpen = readStoredBoolean(NEXT_CHANNEL_ANALYSIS_TREE_STORAGE_KEY, false);
let nextChannelFunctionInventoryTreeOpen = readStoredBoolean(NEXT_CHANNEL_FUNCTION_INVENTORY_TREE_STORAGE_KEY, false);
let nextChannelVocAnalysisTreeOpen = readStoredBoolean(NEXT_CHANNEL_VOC_ANALYSIS_TREE_STORAGE_KEY, false);
let nextChannelTaskDefinitionTreeOpen = readStoredBoolean(NEXT_CHANNEL_TASK_DEFINITION_TREE_STORAGE_KEY, false);
let nextChannelRequirementsTreeOpen = readStoredBoolean(NEXT_CHANNEL_REQUIREMENTS_TREE_STORAGE_KEY, false);
let nextChannelPolicyTreeOpen = readStoredBoolean(NEXT_CHANNEL_POLICY_TREE_STORAGE_KEY, false);
let nextBssTreeOpen = readStoredBoolean(NEXT_BSS_TREE_STORAGE_KEY, false);
let sideNavCollapsed = initialSideNavCollapsed();
let workspaceAssistEnabled = readStoredBoolean(WORKSPACE_ASSIST_ENABLED_STORAGE_KEY, true);
let activeWorkspaceAssistTab = "ai";
let workspaceBootstrapped = false;
let llmAccessAuthorized = false;
let llmAccessToken = "";
let siteWriterSettings = { writerMode: "mock", persisted: false, canUpdate: false, updatedAt: "" };
let siteWriterSettingsLoaded = false;
let writerModeUpdateInFlight = false;
let pendingEditSaveModeResolver = null;
let topicScopeDefinitions = {};
let topicScopesLoaded = false;
let requirementTopicCounts = {};
let requirementTopicCountsLoaded = false;
let requirementTopicCountsLoading = false;
let lastAutoBrief = "";
let workspaceDirectionEditMode = false;
let workspaceDirectionSaving = false;
let workspaceDirectionTopic = "";
let rewriteRequestTopic = "";
const liveFeedbackCache = new Map();
const liveFeedbackInFlight = new Map();
const qaReviewReportsByPolicy = new Map();
const sharedQaReviewReportsByPolicy = new Map();
const healthCheckReportsByPolicy = new Map();
const sharedHealthCheckReportsByPolicy = new Map();
const alignmentCheckReportsByPolicy = new Map();
let healthCheckRubric = null;
let piCheckRubric = null;
const DOCUMENT_QA_LOADING_STEPS = [
  {
    label: "문서 구조 읽기",
    detail: "히스토리, 용어, 액터, 유즈케이스, 상태, 프로세스, 기능, 정책 구조를 확인합니다.",
    start: 0,
  },
  {
    label: "개발 관점 점검",
    detail: "상세 설계자가 구현 단위와 판단 기준을 이해할 수 있는지 확인합니다.",
    start: 8,
  },
  {
    label: "QA 관점 점검",
    detail: "정상·예외·제한 흐름과 테스트 경계값을 도출할 수 있는지 확인합니다.",
    start: 22,
  },
  {
    label: "보완 항목 분류",
    detail: "변경, 추가, 삭제 유형으로 조치 가능한 항목만 정리합니다.",
    start: 38,
  },
  {
    label: "우선순위 정리",
    detail: "개발/QA 영향도 기준으로 P1, P2, P3 우선순위를 부여합니다.",
    start: 56,
  },
  {
    label: "검수 결과 정리",
    detail: "LLM 응답을 기다리는 중입니다. 완료되면 결과를 저장하고 화면에 자동 표시합니다.",
    start: 76,
  },
];

function apiPath(path) {
  return `${API_ORIGIN}${path}`;
}

function setAccessGateMessage(text, isError = false) {
  if (!accessGateMessage) return;
  accessGateMessage.textContent = text;
  accessGateMessage.classList.toggle("error", isError);
}

function setAccessMode(mode) {
  const isSignup = mode === "signup";
  const isReset = mode === "reset";
  if (accessLoginForm) accessLoginForm.hidden = isSignup || isReset;
  if (accessSignupForm) accessSignupForm.hidden = !isSignup;
  if (accessResetForm) accessResetForm.hidden = !isReset;
  accessModeLoginButton?.classList.toggle("active", !isSignup && !isReset);
  accessModeSignupButton?.classList.toggle("active", isSignup);
  accessModeResetButton?.classList.toggle("active", isReset);
  const helperText = isSignup
    ? "회원가입 정보를 입력하고 입장 코드를 확인해 주세요."
    : isReset
      ? "가입된 사번과 입장 코드로 새 비밀번호를 설정해 주세요."
      : "사번과 비밀번호로 로그인해 주세요.";
  setAccessGateMessage(helperText);
  window.setTimeout(() => {
    (isSignup ? signupNameInput : isReset ? resetEmployeeIdInput : loginEmployeeIdInput)?.focus();
  }, 0);
}

function setCurrentUser(user) {
  currentUser = user && user.name ? user : null;
  const authorInput = document.querySelector("#author");
  if (authorInput) {
    authorInput.value = currentUser?.name || "Policy Web";
  }
  if (signedInUserName) {
    signedInUserName.textContent = currentUser?.name ? `${currentUser.name}님` : "-";
  }
  if (signedInUserBadge) {
    signedInUserBadge.hidden = !currentUser;
  }
  if (userManagementButton) {
    userManagementButton.hidden = !canCurrentUserManageUsers();
  }
  if (channelPiStatusButton) {
    channelPiStatusButton.hidden = !canCurrentUserViewChannelPiStatus();
  }
  if (!canCurrentUserManageUsers()) {
    closeUserManagementModal();
    closeChannelPiStatusModal();
  }
  applyWriterModeSettings(siteWriterSettings);
  updateTemplateTypeAccess();
  updateCreateAvailability();
  setPreviewActionMode(selectedDraft ? "draft" : selectedName ? "selected" : "empty");
}

function canCurrentUserManageUsers() {
  const employeeId = String(currentUser?.employeeId || "").trim().toLowerCase();
  return Boolean(employeeId && USER_MANAGEMENT_EMPLOYEE_IDS.has(employeeId));
}

function canCurrentUserViewChannelPiStatus() {
  return canCurrentUserManageUsers();
}

function canCurrentUserRunAdminPolicyActions() {
  return canCurrentUserManageUsers();
}

function currentUserRole() {
  const raw = String(currentUser?.role || "user").trim().toLowerCase();
  if (["viewer", "view", "read", "readonly", "read_only", "조회", "조회자"].includes(raw)) return "viewer";
  return "user";
}

function currentUserRoleLabel(role = currentUserRole()) {
  return currentUserRoleFromValue(role) === "viewer" ? "조회자" : "편집자";
}

function canCurrentUserWritePolicies() {
  return Boolean(currentUser) && (canCurrentUserManageUsers() || currentUserRole() !== "viewer");
}

function guardWritePermission(messageText = "조회 권한은 문서 생성·수정·삭제를 실행할 수 없습니다.") {
  if (canCurrentUserWritePolicies()) return true;
  setMessage(messageText, true);
  return false;
}

function guardPolicyAdminAction(messageText = "이 작업은 관리자만 실행할 수 있습니다.") {
  if (canCurrentUserRunAdminPolicyActions()) return true;
  setMessage(messageText, true);
  return false;
}

function updateTemplateTypeAccess() {
  if (!fullTemplateTypeInput) return;
  const adminAllowed = canCurrentUserRunAdminPolicyActions();
  if (!adminAllowed && fullTemplateTypeInput.checked && simpleTemplateTypeInput) {
    simpleTemplateTypeInput.checked = true;
  }
  fullTemplateTypeInput.disabled = !adminAllowed;
  const fullChoice = fullTemplateTypeInput.closest(".choice-card");
  if (fullChoice) {
    fullChoice.classList.toggle("is-disabled", !adminAllowed);
    fullChoice.setAttribute("aria-disabled", String(!adminAllowed));
    fullChoice.title = adminAllowed ? "" : "Full 버전 작성은 관리자만 실행할 수 있습니다.";
  }
}

function showAccessGate() {
  document.body.classList.add("access-locked");
  if (accessGate) accessGate.hidden = false;
}

function hideAccessGate() {
  document.body.classList.remove("access-locked");
  if (accessGate) accessGate.hidden = true;
}

function bootstrapWorkspace() {
  if (workspaceBootstrapped) return;
  workspaceBootstrapped = true;
  renderTopicChips();
  loadTopicScopes();
  loadRequirementTopicCounts();
  loadHealth();
  loadPolicies();
}

async function checkAccessStatus() {
  const response = await fetch(apiPath("/api/access/status"));
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "로그인 상태를 확인할 수 없습니다.");
  }
  return {
    authorized: Boolean(data.authorized),
    user: data.user || null,
  };
}

function getSelectedWriterMode() {
  return writerModeInputs.find((input) => input.checked)?.value || "mock";
}

function normalizeWriterModeValue(mode) {
  return String(mode || "mock").trim().toLowerCase() === "llm" ? "llm" : "mock";
}

function getSiteWriterMode() {
  return normalizeWriterModeValue(siteWriterSettings?.writerMode);
}

function canCurrentUserUpdateWriterModeSettings() {
  return Boolean(currentUser) && canCurrentUserManageUsers() && Boolean(siteWriterSettings?.canUpdate);
}

function setWriterMode(mode) {
  const normalizedMode = normalizeWriterModeValue(mode);
  writerModeInputs.forEach((input) => {
    input.checked = input.value === normalizedMode;
  });
}

function applyWriterModeSettings(settings = siteWriterSettings) {
  const writerMode = normalizeWriterModeValue(settings?.writerMode);
  siteWriterSettings = {
    writerMode,
    persisted: Boolean(settings?.persisted),
    canUpdate: Boolean(settings?.canUpdate),
    updatedAt: String(settings?.updatedAt || ""),
  };
  siteWriterSettingsLoaded = true;
  setWriterMode(writerMode);

  const canUpdate = canCurrentUserUpdateWriterModeSettings();
  writerModeInputs.forEach((input) => {
    input.disabled = !canUpdate || writerModeUpdateInFlight;
  });
  if (writerModePanel) {
    writerModePanel.classList.toggle("is-readonly", !canUpdate);
    writerModePanel.classList.toggle("is-saving", writerModeUpdateInFlight);
    writerModePanel.setAttribute("aria-disabled", String(!canUpdate));
    writerModePanel.title = canUpdate
      ? "관리자 설정입니다. 변경하면 모든 사용자에게 적용됩니다."
      : "LLM 사용 여부는 관리자만 변경할 수 있으며 모든 사용자에게 공통 적용됩니다.";
  }
}

async function refreshSiteWriterModeSettings({ silent = true } = {}) {
  if (!accessAuthorized) {
    applyWriterModeSettings({ writerMode: "mock", persisted: false, canUpdate: false, updatedAt: "" });
    return siteWriterSettings;
  }
  try {
    const response = await fetch(apiPath("/api/site-settings"));
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "LLM 사용 설정을 불러올 수 없습니다.");
    }
    applyWriterModeSettings(data.settings || {});
  } catch (error) {
    applyWriterModeSettings({ ...siteWriterSettings, canUpdate: false });
    if (!silent) {
      setMessage(error.message || "LLM 사용 설정을 불러올 수 없습니다.", true);
    }
  }
  return siteWriterSettings;
}

async function saveSiteWriterMode(mode, token = "") {
  const writerMode = normalizeWriterModeValue(mode);
  writerModeUpdateInFlight = true;
  applyWriterModeSettings(siteWriterSettings);
  try {
    const response = await fetch(apiPath("/api/site-settings/writer-mode"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(
        withClientSession({
          writerMode,
          llmAccessToken: writerMode === "llm" ? token : "",
        })
      ),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "LLM 사용 설정을 저장할 수 없습니다.");
    }
    applyWriterModeSettings(data.settings || {});
    return siteWriterSettings;
  } finally {
    writerModeUpdateInFlight = false;
    applyWriterModeSettings(siteWriterSettings);
  }
}

async function requestLlmAccess() {
  llmAccessAuthorized = false;
  llmAccessToken = "";
  const key = window.prompt("LLM 사용 인증키를 입력해 주세요.");
  if (!key) {
    setMessage("LLM 사용 인증이 취소되어 미사용 상태로 유지합니다.", true);
    return false;
  }

  const response = await fetch(apiPath("/api/access/llm-login"), {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify(withClientSession({ key: String(key).trim() })),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "LLM 사용 인증에 실패했습니다.");
  }
  llmAccessAuthorized = true;
  llmAccessToken = String(data.token || "");
  return true;
}

async function ensureWriterModeAccess(writerMode) {
  if (writerMode !== "llm") return true;
  if (getSiteWriterMode() === "llm") return true;
  if (llmAccessAuthorized && llmAccessToken) return true;
  if (!canCurrentUserUpdateWriterModeSettings()) {
    setMessage("LLM 사용은 관리자 설정으로만 변경할 수 있습니다.", true);
    return false;
  }
  return requestLlmAccess();
}

async function buildLlmControlledPayload(payload = {}) {
  const writerMode = getSelectedWriterMode();
  const allowed = await ensureWriterModeAccess(writerMode);
  if (!allowed) return null;
  return withClientSession({
    ...payload,
    writerMode,
    llmAccessToken: writerMode === "llm" ? llmAccessToken : "",
  });
}

async function initializeAccessGate() {
  try {
    const status = await checkAccessStatus();
    accessAuthorized = status.authorized;
    setCurrentUser(status.user);
  } catch (error) {
    accessAuthorized = false;
    setCurrentUser(null);
    setAccessGateMessage(error.message || "로그인 상태를 확인하지 못했습니다.", true);
  }

  if (accessAuthorized) {
    hideAccessGate();
    llmAccessAuthorized = false;
    llmAccessToken = "";
    await refreshSiteWriterModeSettings();
    bootstrapWorkspace();
  } else {
    setAccessMode("login");
    showAccessGate();
  }
}

function resolveClientSessionId() {
  const key = "ncPolicyClientSessionId";
  try {
    const existing = window.localStorage.getItem(key);
    if (existing) return existing;
    const generated =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `web-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    window.localStorage.setItem(key, generated);
    return generated;
  } catch (error) {
    return `web-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }
}

function readStoredBoolean(key, fallback) {
  try {
    const value = window.localStorage.getItem(key);
    if (value === "true") return true;
    if (value === "false") return false;
  } catch (_error) {
    // Keep the UI usable even if localStorage is unavailable.
  }
  return Boolean(fallback);
}

function applyTopicTreeCollapsedDefault() {
  try {
    if (window.localStorage.getItem(TOPIC_TREE_COLLAPSED_DEFAULT_APPLIED_KEY) === "true") {
      return;
    }
    [
      NEXT_CHANNEL_TREE_STORAGE_KEY,
      NEXT_CHANNEL_ANALYSIS_TREE_STORAGE_KEY,
      NEXT_CHANNEL_FUNCTION_INVENTORY_TREE_STORAGE_KEY,
      NEXT_CHANNEL_VOC_ANALYSIS_TREE_STORAGE_KEY,
      NEXT_CHANNEL_TASK_DEFINITION_TREE_STORAGE_KEY,
      NEXT_CHANNEL_REQUIREMENTS_TREE_STORAGE_KEY,
      NEXT_CHANNEL_POLICY_TREE_STORAGE_KEY,
      NEXT_BSS_TREE_STORAGE_KEY,
    ].forEach((key) => window.localStorage.setItem(key, "false"));
    window.localStorage.setItem(TOPIC_TREE_COLLAPSED_DEFAULT_APPLIED_KEY, "true");
  } catch (_error) {
    // Non-critical first-run preference only.
  }
}

function initialSideNavCollapsed() {
  try {
    if (window.localStorage.getItem(SIDE_NAV_COLLAPSED_DEFAULT_APPLIED_KEY) !== "true") {
      window.localStorage.setItem(SIDE_NAV_COLLAPSED_DEFAULT_APPLIED_KEY, "true");
      window.localStorage.setItem(SIDE_NAV_COLLAPSED_STORAGE_KEY, "true");
      return true;
    }
  } catch (_error) {
    return true;
  }
  return readStoredBoolean(SIDE_NAV_COLLAPSED_STORAGE_KEY, true);
}

function storeBoolean(key, value) {
  try {
    window.localStorage.setItem(key, value ? "true" : "false");
  } catch (_error) {
    // Non-critical preference only.
  }
}

function isCompactWorkspaceViewport() {
  if (typeof window === "undefined") return false;
  if (window.matchMedia) {
    return window.matchMedia(COMPACT_WORKSPACE_QUERY).matches;
  }
  return window.innerWidth <= 1280;
}

function focusWorkspaceOnCompact(element = resultArea) {
  if (!isCompactWorkspaceViewport()) return;
  if (!sideNavCollapsed) {
    setSideNavCollapsed(true);
  }
  if (!element) return;
  window.requestAnimationFrame(() => {
    const rect = element.getBoundingClientRect();
    const top = Math.max(0, rect.top + window.scrollY - 12);
    window.scrollTo({ top, behavior: "smooth" });
  });
}

function setSideNavCollapsed(collapsed, options = {}) {
  sideNavCollapsed = Boolean(collapsed);
  appShell?.classList.toggle("side-nav-collapsed", sideNavCollapsed);
  if (sideNavToggle) {
    const label = sideNavCollapsed ? "주제 목록 펼치기" : "주제 목록 접기";
    sideNavToggle.setAttribute("aria-expanded", String(!sideNavCollapsed));
    sideNavToggle.setAttribute("aria-label", label);
    sideNavToggle.setAttribute("title", label);
    const text = sideNavToggle.querySelector(".side-nav-toggle-text");
    if (text) text.textContent = sideNavCollapsed ? "펼치기" : "접기";
  }
  if (options.persist) {
    storeBoolean(SIDE_NAV_COLLAPSED_STORAGE_KEY, sideNavCollapsed);
  }
}

function setSubmitButtonsDisabled(disabled) {
  if (submitButton) submitButton.disabled = Boolean(disabled);
  if (requestQuickSubmitButton) requestQuickSubmitButton.disabled = Boolean(disabled);
}

function setWorkspaceAssistTab(tabName) {
  const normalized = tabName === "human" ? "human" : "ai";
  activeWorkspaceAssistTab = normalized;
  workspaceAssistTabButtons.forEach((button) => {
    const active = button.dataset.assistTab === normalized;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  workspaceAssistPanes.forEach((pane) => {
    const active = pane.dataset.assistPane === normalized;
    pane.classList.toggle("active", active);
    pane.hidden = !active;
  });
  updateCommentWorkspaceToolsVisibility();
}

function updateCommentWorkspaceToolsVisibility() {
  if (!commentWorkspaceTools) return;
  const visible = workspaceAssistEnabled && !workspaceAssistPanel?.hidden && activeWorkspaceAssistTab === "human";
  commentWorkspaceTools.hidden = !visible;
  if (!visible) {
    if (editorCommentFilterMenu) editorCommentFilterMenu.open = false;
    if (editorCommentSortMenu) editorCommentSortMenu.open = false;
  }
}

function setWorkspaceAssistEnabled(enabled, options = {}) {
  workspaceAssistEnabled = Boolean(enabled);
  workspaceAssistModeInputs.forEach((input) => {
    input.checked = input.value === (workspaceAssistEnabled ? "on" : "off");
  });
  if (options.persist) {
    storeBoolean(WORKSPACE_ASSIST_ENABLED_STORAGE_KEY, workspaceAssistEnabled);
  }
  if (!workspaceAssistEnabled) {
    updateCommentWorkspaceToolsVisibility();
    hideWorkspaceAssistPanel();
    return;
  }
  if (selectedName || selectedDraft) {
    updateWorkspaceAssistPanel();
  }
}

function showWorkspaceAssistPanel() {
  if (!workspaceAssistPanel) return;
  if (!workspaceAssistEnabled) {
    hideWorkspaceAssistPanel();
    return;
  }
  workspaceAssistPanel.hidden = false;
  resultsLayout?.classList.add("has-assist");
  updateCommentWorkspaceToolsVisibility();
}

function currentPolicyStorageHash() {
  return selectedPolicyItem()?.contentHash || selectedDraft?.id || "draft";
}

function editorVersionStorageKey(prefix) {
  const name = selectedName || selectedDraft?.id || "none";
  return `${prefix}.${name}.${currentPolicyStorageHash()}`;
}

function editorCommentStorageTopicKey() {
  const item = selectedPolicyItem();
  return item?.topic || selectedDraft?.topic || selectedName || "none";
}

function editorStorageKey(prefix) {
  if (prefix === EDITOR_COMMENT_STORAGE_PREFIX) {
    return `${prefix}.topic.${editorCommentStorageTopicKey()}`;
  }
  return editorVersionStorageKey(prefix);
}

function editorCommentPolicyName() {
  return selectedName || "";
}

function editorCommentsUseServer() {
  return Boolean(editorCommentPolicyName());
}

function editorCommentMigrationKey() {
  return `${EDITOR_COMMENT_MIGRATION_PREFIX}.topic.${editorCommentStorageTopicKey()}`;
}

function readStoredJsonArray(key) {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function storeJsonArray(key, items) {
  try {
    window.localStorage.setItem(key, JSON.stringify(Array.isArray(items) ? items : []));
  } catch (_error) {
    // 편집 보조 메모 저장 실패는 문서 저장 흐름을 막지 않는다.
  }
}

function loadEditorAssistState() {
  let cachedComments = readStoredJsonArray(editorStorageKey(EDITOR_COMMENT_STORAGE_PREFIX));
  if (!cachedComments.length) {
    const legacyCachedComments = readStoredJsonArray(editorVersionStorageKey(EDITOR_COMMENT_STORAGE_PREFIX));
    if (legacyCachedComments.length) {
      cachedComments = legacyCachedComments;
      storeJsonArray(editorStorageKey(EDITOR_COMMENT_STORAGE_PREFIX), cachedComments);
    }
  }
  editorComments = cachedComments;
  editorSuggestions = readStoredJsonArray(editorStorageKey(EDITOR_SUGGESTION_STORAGE_PREFIX));
  selectedEditorContext = null;
  selectedEditorCommentId = "";
  renderEditorAssistPanels();
  applyEditorCommentHighlights();
  if (editorCommentsUseServer()) {
    refreshSharedEditorComments({ cachedComments });
  }
}

function saveEditorComments() {
  storeJsonArray(editorStorageKey(EDITOR_COMMENT_STORAGE_PREFIX), editorComments);
}

function saveEditorSuggestions() {
  storeJsonArray(editorStorageKey(EDITOR_SUGGESTION_STORAGE_PREFIX), editorSuggestions);
}

async function refreshSharedEditorComments(options = {}) {
  const policyName = editorCommentPolicyName();
  if (!policyName) return;
  const loadToken = ++editorCommentLoadToken;
  const cachedComments = Array.isArray(options.cachedComments) ? options.cachedComments : [];
  editorCommentsSyncing = true;
  try {
    const response = await fetch(apiPath(`/api/policies/comments?name=${encodeURIComponent(policyName)}`));
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "공동 코멘트를 불러오지 못했습니다.");
    }
    if (loadToken !== editorCommentLoadToken || editorCommentPolicyName() !== policyName) return;
    const sharedComments = Array.isArray(data.comments) ? data.comments : [];
    const migrationKey = editorCommentMigrationKey();
    const migrated = readStoredBoolean(migrationKey, false);
    if (!sharedComments.length && cachedComments.length && !migrated) {
      storeBoolean(migrationKey, true);
      await persistEditorCommentAction("replace", { comments: cachedComments }, { policyName, allowEmpty: true, silent: true });
      return;
    }
    storeBoolean(migrationKey, true);
    editorComments = sharedComments;
    selectedEditorCommentId = "";
    saveEditorComments();
    renderEditorCommentList();
  } catch (error) {
    console.warn(error);
  } finally {
    if (loadToken === editorCommentLoadToken) {
      editorCommentsSyncing = false;
    }
  }
}

async function persistEditorCommentAction(action, payload = {}, options = {}) {
  const policyName = options.policyName || editorCommentPolicyName();
  if (!policyName) return null;
  const body = withClientSession({
    name: policyName,
    contentHash: currentPolicyStorageHash(),
    action,
    ...payload,
  });
  const response = await fetch(apiPath("/api/policies/comments"), {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "공동 코멘트 저장에 실패했습니다.");
  }
  if (editorCommentPolicyName() === policyName && Array.isArray(data.comments)) {
    editorComments = data.comments;
    if (!editorComments.some((comment) => comment.id === selectedEditorCommentId)) {
      selectedEditorCommentId = "";
    }
    saveEditorComments();
    renderEditorCommentList();
  }
  return data;
}

function handleEditorCommentSyncError(error) {
  console.warn(error);
  setMessage(error.message || "공동 코멘트를 저장하지 못했습니다. 화면에는 임시로 남겨두었습니다.", true);
}

function jsonHeaders() {
  return {
    "Content-Type": "application/json",
    "X-NC-Session-Id": CLIENT_SESSION_ID,
  };
}

accessModeLoginButton?.addEventListener("click", () => setAccessMode("login"));
accessModeSignupButton?.addEventListener("click", () => setAccessMode("signup"));
accessModeResetButton?.addEventListener("click", () => setAccessMode("reset"));

if (accessLoginForm) {
  accessLoginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const employeeId = String(loginEmployeeIdInput?.value || "").trim();
    const password = String(loginPasswordInput?.value || "");
    if (!employeeId) {
      setAccessGateMessage("사번을 입력해 주세요.", true);
      loginEmployeeIdInput?.focus();
      return;
    }
    if (!password) {
      setAccessGateMessage("비밀번호를 입력해 주세요.", true);
      loginPasswordInput?.focus();
      return;
    }

    if (accessLoginButton) accessLoginButton.disabled = true;
    setAccessGateMessage("로그인하고 있습니다.");
    try {
      const response = await fetch(apiPath("/api/access/login"), {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify(withClientSession({ employeeId, password })),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || "로그인할 수 없습니다.");
      }
      accessAuthorized = true;
      setCurrentUser(data.user || null);
      hideAccessGate();
      setAccessGateMessage("로그인되었습니다.");
      if (loginPasswordInput) loginPasswordInput.value = "";
      await refreshSiteWriterModeSettings();
      bootstrapWorkspace();
    } catch (error) {
      setAccessGateMessage(error.message || "로그인할 수 없습니다.", true);
    } finally {
      if (accessLoginButton) accessLoginButton.disabled = false;
    }
  });
}

if (accessSignupForm) {
  accessSignupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = String(signupNameInput?.value || "").trim();
    const employeeId = String(signupEmployeeIdInput?.value || "").trim();
    const password = String(signupPasswordInput?.value || "");
    const passwordConfirm = String(signupPasswordConfirmInput?.value || "");
    const code = String(signupEntryCodeInput?.value || "").trim();
    if (!name) {
      setAccessGateMessage("이름을 입력해 주세요.", true);
      signupNameInput?.focus();
      return;
    }
    if (!employeeId) {
      setAccessGateMessage("사번을 입력해 주세요.", true);
      signupEmployeeIdInput?.focus();
      return;
    }
    if (!password) {
      setAccessGateMessage("비밀번호를 입력해 주세요.", true);
      signupPasswordInput?.focus();
      return;
    }
    if (!passwordConfirm) {
      setAccessGateMessage("비밀번호 확인을 입력해 주세요.", true);
      signupPasswordConfirmInput?.focus();
      return;
    }
    if (password !== passwordConfirm) {
      setAccessGateMessage("비밀번호와 비밀번호 확인이 일치하지 않습니다.", true);
      signupPasswordConfirmInput?.focus();
      return;
    }
    if (!code) {
      setAccessGateMessage("입장 코드를 입력해 주세요.", true);
      signupEntryCodeInput?.focus();
      return;
    }

    if (accessSignupButton) accessSignupButton.disabled = true;
    setAccessGateMessage("계정을 생성하고 있습니다.");
    try {
      const response = await fetch(apiPath("/api/access/signup"), {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify(withClientSession({ name, employeeId, password, passwordConfirm, code })),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || "계정을 만들 수 없습니다.");
      }
      if (!data.authorized) {
        setAccessMode("login");
        setAccessGateMessage("계정이 생성되었습니다. 관리자 승인 후 이용할 수 있습니다.");
        return;
      }
      accessAuthorized = true;
      setCurrentUser(data.user || null);
      hideAccessGate();
      setAccessGateMessage("계정 생성과 로그인이 완료되었습니다.");
      if (signupPasswordInput) signupPasswordInput.value = "";
      if (signupPasswordConfirmInput) signupPasswordConfirmInput.value = "";
      if (signupEntryCodeInput) signupEntryCodeInput.value = "";
      await refreshSiteWriterModeSettings();
      bootstrapWorkspace();
    } catch (error) {
      setAccessGateMessage(error.message || "계정을 만들 수 없습니다.", true);
    } finally {
      if (accessSignupButton) accessSignupButton.disabled = false;
    }
  });
}

if (accessResetForm) {
  accessResetForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const employeeId = String(resetEmployeeIdInput?.value || "").trim();
    const password = String(resetPasswordInput?.value || "");
    const passwordConfirm = String(resetPasswordConfirmInput?.value || "");
    const code = String(resetEntryCodeInput?.value || "").trim();
    if (!employeeId) {
      setAccessGateMessage("사번을 입력해 주세요.", true);
      resetEmployeeIdInput?.focus();
      return;
    }
    if (!password) {
      setAccessGateMessage("새 비밀번호를 입력해 주세요.", true);
      resetPasswordInput?.focus();
      return;
    }
    if (!passwordConfirm) {
      setAccessGateMessage("새 비밀번호 확인을 입력해 주세요.", true);
      resetPasswordConfirmInput?.focus();
      return;
    }
    if (password !== passwordConfirm) {
      setAccessGateMessage("비밀번호와 비밀번호 확인이 일치하지 않습니다.", true);
      resetPasswordConfirmInput?.focus();
      return;
    }
    if (!code) {
      setAccessGateMessage("입장 코드를 입력해 주세요.", true);
      resetEntryCodeInput?.focus();
      return;
    }

    if (accessResetButton) accessResetButton.disabled = true;
    setAccessGateMessage("비밀번호를 재설정하고 있습니다.");
    try {
      const response = await fetch(apiPath("/api/access/reset-password"), {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify(withClientSession({ employeeId, password, passwordConfirm, code })),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || "비밀번호를 재설정할 수 없습니다.");
      }
      accessAuthorized = true;
      setCurrentUser(data.user || null);
      hideAccessGate();
      setAccessGateMessage("비밀번호 재설정과 로그인이 완료되었습니다.");
      if (resetPasswordInput) resetPasswordInput.value = "";
      if (resetPasswordConfirmInput) resetPasswordConfirmInput.value = "";
      if (resetEntryCodeInput) resetEntryCodeInput.value = "";
      await refreshSiteWriterModeSettings();
      bootstrapWorkspace();
    } catch (error) {
      setAccessGateMessage(error.message || "비밀번호를 재설정할 수 없습니다.", true);
    } finally {
      if (accessResetButton) accessResetButton.disabled = false;
    }
  });
}

accessLogoutButton?.addEventListener("click", async () => {
  try {
    await fetch(apiPath("/api/access/logout"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({})),
    });
  } catch (_error) {
    // Logging out should always return the browser to the login gate.
  }
  accessAuthorized = false;
  setCurrentUser(null);
  window.location.reload();
});

writerModeInputs.forEach((input) => {
  input.addEventListener("change", async () => {
    const previousMode = getSiteWriterMode();
    if (!canCurrentUserUpdateWriterModeSettings()) {
      setWriterMode(previousMode);
      setMessage("LLM 사용 여부는 관리자만 변경할 수 있습니다.", true);
      return;
    }
    if (input.value === "mock" && input.checked) {
      llmAccessAuthorized = false;
      llmAccessToken = "";
      try {
        await saveSiteWriterMode("mock");
        setMessage("LLM 사용 설정을 미사용으로 저장했습니다. 모든 사용자에게 적용됩니다.");
        trackUserEvent("llm_mode_changed", { mode: "mock", scope: "site" });
      } catch (error) {
        setWriterMode(previousMode);
        setMessage(error.message || "LLM 사용 설정 저장에 실패했습니다.", true);
      }
      return;
    }
    if (input.value !== "llm" || !input.checked) return;
    try {
      const ok = await requestLlmAccess();
      if (!ok) {
        setWriterMode(previousMode);
        return;
      }
      await saveSiteWriterMode("llm", llmAccessToken);
      setMessage("LLM 사용 설정을 저장했습니다. 모든 사용자에게 적용됩니다.");
      trackUserEvent("llm_mode_changed", { mode: "llm", scope: "site" });
    } catch (error) {
      setWriterMode(previousMode);
      setMessage(error.message || "LLM 사용 설정 저장에 실패했습니다.", true);
    }
  });
});

function withClientSession(payload = {}) {
  const nextPayload = {
    ...payload,
    clientSessionId: CLIENT_SESSION_ID,
  };
  if (normalizeWriterModeValue(nextPayload.writerMode) === "llm" && getSiteWriterMode() === "llm") {
    nextPayload.useSiteWriterMode = true;
  }
  return nextPayload;
}

function trackUserEvent(eventName, details = {}) {
  if (!eventName) return;
  try {
    fetch(apiPath("/api/usage-events"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({ event: eventName, details })),
      keepalive: true,
    }).catch(() => {});
  } catch (_error) {
    // Usage logging must never block the main workflow.
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!guardWritePermission("조회 권한은 새 문서 작성을 실행할 수 없습니다.")) {
    return;
  }
  const formData = new FormData(form);
  const topic = getCurrentRequestTopic(formData);
  if (!topic) {
    setMessage("좌측에서 작성할 정책서 주제를 먼저 선택해 주세요.", true);
    return;
  }
  const rewriteExisting = isRewriteRequestForTopic(topic);
  const templateType = formData.get("templateType") || "simple";
  if (rewriteExisting && !guardPolicyAdminAction("정책서 다시 작성은 관리자만 실행할 수 있습니다.")) {
    return;
  }
  if (templateType === "full" && !guardPolicyAdminAction("Full 버전 작성은 관리자만 실행할 수 있습니다.")) {
    return;
  }

  setMessage("정책서 생성 작업을 시작합니다.");
  setSubmitButtonsDisabled(true);

  const writerMode = getSelectedWriterMode();
  try {
    const allowed = await ensureWriterModeAccess(writerMode);
    if (!allowed) {
      setSubmitButtonsDisabled(false);
      return;
    }
  } catch (error) {
    setSubmitButtonsDisabled(false);
    setMessage(error.message || "LLM 사용 인증에 실패했습니다.", true);
    return;
  }

  const payload = {
    topic,
    templateType,
    reviewMode: formData.get("reviewMode") || "auto",
    inspectionMode: formData.get("inspectionMode") || "chapter-final",
    writerMode,
    llmAccessToken: writerMode === "llm" ? llmAccessToken : "",
    brief: formData.get("brief"),
    author: formData.get("author"),
    status: formData.get("status"),
    rewriteExisting,
  };

  try {
    const response = await fetch(apiPath("/api/policies"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession(payload)),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "정책서 생성에 실패했습니다.");
    }
    if (data.job) {
      activeJobId = data.job.id;
      clearRewriteRequest();
      openProgressModal(data.job);
      setMessage("정책서 생성이 진행 중입니다. 작성 현황 팝업에서 단계를 확인하세요.");
      startProgressPolling(activeJobId);
      return;
    }
    clearRewriteRequest();
    setMessage(`생성 완료: ${data.item.name}`);
    await loadPolicies(data.item.name);
  } catch (error) {
    setMessage(error.message, true);
    setSubmitButtonsDisabled(false);
    closeProgressPolling();
  }
});

progressCloseButton?.addEventListener("click", () => {
  closeOrCancelProgressModal();
});

progressCancelButton?.addEventListener("click", () => {
  closeOrCancelProgressModal();
});

function startProgressPolling(jobId) {
  closeProgressPolling();
  progressTimer = window.setInterval(() => pollJob(jobId), 1000);
  startProgressHeartbeat(jobId);
  pollJob(jobId);
}

function closeProgressPolling() {
  if (progressTimer) {
    window.clearInterval(progressTimer);
    progressTimer = null;
  }
  if (progressHeartbeatTimer) {
    window.clearInterval(progressHeartbeatTimer);
    progressHeartbeatTimer = null;
  }
}

function startProgressHeartbeat(jobId) {
  if (!jobId) return;
  sendJobHeartbeat(jobId);
  progressHeartbeatTimer = window.setInterval(() => sendJobHeartbeat(jobId), JOB_HEARTBEAT_INTERVAL_MS);
}

async function sendJobHeartbeat(jobId) {
  if (!jobId) return;
  try {
    await fetch(apiPath(`/api/jobs/${encodeURIComponent(jobId)}/heartbeat`), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({ active: true })),
      keepalive: true,
    });
  } catch (error) {
    // The server watchdog will cancel orphaned work if heartbeats stop.
  }
}

async function closeOrCancelProgressModal() {
  const job = currentProgressJob;
  if (!job || !isCancelableJob(job)) {
    progressModal.hidden = true;
    return;
  }
  if (!guardWritePermission("조회 권한은 진행 중 작업 중단을 실행할 수 없습니다.")) return;

  const confirmed = window.confirm(
    "정책서 작성을 중단할까요?\n사용자 검토 대기 중이면 즉시 멈추고, LLM 호출 중이면 현재 호출이 끝난 직후 중단됩니다.\n지금까지 작성된 중간 결과와 체크포인트는 보관됩니다."
  );
  if (!confirmed) return;

  progressCloseButton.disabled = true;
  if (progressCancelButton) progressCancelButton.disabled = true;
  setMessage("정책서 생성 중단을 요청했습니다. 중간 결과를 보관합니다.");
  try {
    const response = await fetch(apiPath(`/api/jobs/${encodeURIComponent(job.id)}/cancel`), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({ reason: "progress_modal_closed" })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "작업 중단에 실패했습니다.");
    }
    currentProgressJob = data.job;
    progressModal.hidden = true;
    if (data.job?.status === "canceled") {
      closeProgressPolling();
      setSubmitButtonsDisabled(false);
      revisionButton.disabled = false;
      setMessage(data.job.message || "정책서 작업이 중단되었습니다.");
    } else {
      startProgressPolling(job.id);
      setMessage("정책서 작업 중단을 요청했습니다. 보관 상태로 전환하는 동안 잠시만 기다려 주세요.");
    }
    await loadPolicies(selectedName, { autoSelect: false });
    const draft = latestDraftForTopic(data.job?.topic || job.topic);
    if (draft) {
      selectDraft(draft);
    } else if (!selectedName || !currentItems.some((item) => item.name === selectedName)) {
      clearPreview();
    }
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    progressCloseButton.disabled = false;
    if (progressCancelButton) progressCancelButton.disabled = false;
  }
}

function isCancelableJob(job) {
  return ["queued", "running", "waiting_review", "review", "retry"].includes(job.status);
}

async function pollJob(jobId) {
  try {
    const response = await fetch(apiPath(`/api/jobs/${encodeURIComponent(jobId)}`));
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "작업 상태를 불러오지 못했습니다.");
    }
    renderProgress(data.job);
    if (data.job.status === "completed") {
      closeProgressPolling();
      setSubmitButtonsDisabled(false);
      revisionButton.disabled = false;
      if (selectionRevisionSubmitButton) selectionRevisionSubmitButton.disabled = false;
      revisionRequest.value = "";
      const doneLabel = data.job.kind === "revision" ? "수정 완료" : "생성 완료";
      setMessage(`${doneLabel}: ${data.job.result?.name || "정책서"}`);
      if (data.job.result?.name) {
        await loadPolicies(data.job.result.name);
        if (data.job.kind === "revision" && pendingQaActionCheck) {
          if (pendingQaActionCheck.report) {
            qaReviewReportsByPolicy.set(data.job.result.name, pendingQaActionCheck.report);
            latestQaReviewReport = pendingQaActionCheck.report;
          }
          await checkDocumentQaActionStatus({ name: data.job.result.name, items: pendingQaActionCheck.items, manual: false });
          pendingQaActionCheck = null;
        }
      } else {
        await loadPolicies();
      }
    }
    if (data.job.status === "canceled") {
      closeProgressPolling();
      setSubmitButtonsDisabled(false);
      revisionButton.disabled = false;
      if (selectionRevisionSubmitButton) selectionRevisionSubmitButton.disabled = false;
      setMessage(data.job.message || "작업이 중단되었습니다.");
      await loadPolicies(selectedName, { autoSelect: false });
      const draft = latestDraftForTopic(data.job.topic);
      if (draft) {
        selectDraft(draft);
      }
    }
    if (data.job.status === "error") {
      closeProgressPolling();
      setSubmitButtonsDisabled(false);
      revisionButton.disabled = false;
      if (selectionRevisionSubmitButton) selectionRevisionSubmitButton.disabled = false;
      setMessage(data.job.error || data.job.message || "작업 중 오류가 발생했습니다.", true);
    }
  } catch (error) {
    closeProgressPolling();
    setSubmitButtonsDisabled(false);
    revisionButton.disabled = false;
    if (selectionRevisionSubmitButton) selectionRevisionSubmitButton.disabled = false;
    setMessage(error.message, true);
  } finally {
  }
}

refreshButton.addEventListener("click", () => {
  loadPolicies(selectedName);
});

rewritePolicyButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 다시 작성을 실행할 수 없습니다.")) return;
  if (!guardPolicyAdminAction("정책서 다시 작성은 관리자만 실행할 수 있습니다.")) return;
  startRewriteRequestFromSelectedPolicy();
});

fullVersionButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 Full 버전 작성을 실행할 수 없습니다.")) return;
  if (!guardPolicyAdminAction("Full 버전 전환은 관리자만 실행할 수 있습니다.")) return;
  openFullVersionModal();
});

fullVersionCloseButton?.addEventListener("click", closeFullVersionModal);
fullVersionCancelButton?.addEventListener("click", closeFullVersionModal);
fullVersionModal?.addEventListener("click", (event) => {
  if (event.target === fullVersionModal) closeFullVersionModal();
});
fullVersionStartButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 Full 버전 작성을 실행할 수 없습니다.")) return;
  if (!guardPolicyAdminAction("Full 버전 전환은 관리자만 실행할 수 있습니다.")) return;
  startFullVersionFromSimplePolicy();
});

uploadHtmlButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 HTML 업로드를 실행할 수 없습니다.")) return;
  if (isEditing) {
    setMessage("직접 편집 중에는 HTML 업로드를 진행할 수 없습니다. 편집을 완료하거나 취소해 주세요.", true);
    return;
  }
  trackUserEvent("html_upload_button_clicked", { selectedName });
  uploadHtmlInput?.click();
});

uploadHtmlInput?.addEventListener("change", () => {
  const file = uploadHtmlInput.files?.[0];
  if (file) uploadHtmlFile(file);
});

uploadJsonButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 JSON 업로드를 실행할 수 없습니다.")) return;
  if (isEditing) {
    setMessage("직접 편집 중에는 JSON 업로드를 진행할 수 없습니다. 편집을 완료하거나 취소해 주세요.", true);
    return;
  }
  trackUserEvent("json_upload_button_clicked", { selectedName });
  uploadJsonInput?.click();
});

uploadJsonInput?.addEventListener("change", () => {
  const file = uploadJsonInput.files?.[0];
  if (file) uploadJsonFile(file);
});

downloadLink?.addEventListener("click", () => {
  if (!selectedName) return;
  trackUserEvent("html_downloaded", { selectedName, href: downloadLink.href });
});

jsonDownloadLink?.addEventListener("click", async (event) => {
  event.preventDefault();
  const targetName = selectedName || selectedDraft?.id || "";
  if (!targetName) return;
  const href = jsonDownloadLink.getAttribute("href") || "";
  if (!href || href === "#") {
    setMessage("다운로드할 JSON 파일이 아직 준비되지 않았습니다.", true);
    return;
  }
  try {
    const response = await fetch(href, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("JSON 파일을 찾을 수 없습니다.");
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = jsonDownloadLink.getAttribute("download") || "policy.json";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
    trackUserEvent("json_downloaded", { selectedName: targetName, href });
  } catch (error) {
    setMessage("JSON 파일이 없거나 아직 생성되지 않았습니다. 문서를 다시 선택하거나 새로고침 후 확인해 주세요.", true);
    jsonDownloadLink.href = "#";
    jsonDownloadLink.hidden = true;
    jsonDownloadLink.setAttribute("aria-disabled", "true");
    trackUserEvent("json_download_failed", { selectedName: targetName, href, error: error.message });
  }
});

serviceHealthButton?.addEventListener("click", () => {
  trackUserEvent("service_health_opened", {});
  openServiceHealthModal();
});

channelPiStatusButton?.addEventListener("click", () => {
  if (!canCurrentUserViewChannelPiStatus()) {
    setMessage("채널 PI 현황은 관리자만 확인할 수 있습니다.", true);
    return;
  }
  trackUserEvent("channel_pi_status_opened", {});
  openChannelPiStatusPage({ force: false });
});

channelPiHomeButton?.addEventListener("click", () => {
  closeChannelPiStatusModal();
});

channelPiDiagnoseButton?.addEventListener("click", () => {
  loadChannelPiStatus({ force: true });
});

channelPiArea?.addEventListener("click", (event) => {
  if (event.target === channelPiArea) {
    closeChannelPiStatusModal();
  }
});

serviceHealthRefreshButton?.addEventListener("click", () => {
  loadServiceHealth();
});

serviceLockCleanupButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 서비스 기록 정리를 실행할 수 없습니다.")) return;
  cleanupServiceLocks();
});

serviceHealthCloseButton?.addEventListener("click", () => {
  closeServiceHealthModal();
});

serviceHealthModal?.addEventListener("click", (event) => {
  if (event.target === serviceHealthModal) {
    closeServiceHealthModal();
  }
});

userManagementButton?.addEventListener("click", () => {
  trackUserEvent("user_management_opened", {});
  openUserManagementModal();
});

userManagementRefreshButton?.addEventListener("click", () => {
  loadUserManagement();
});

userManagementCloseButton?.addEventListener("click", () => {
  closeUserManagementModal();
});

userManagementModal?.addEventListener("click", (event) => {
  if (event.target === userManagementModal) {
    closeUserManagementModal();
  }
});

userManagementList?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-user-withdraw]");
  if (!button) return;
  const employeeId = button.getAttribute("data-employee-id") || "";
  const name = button.getAttribute("data-user-name") || employeeId;
  withdrawManagedUser(employeeId, name, button);
});

userManagementList?.addEventListener("change", (event) => {
  const select = event.target.closest("[data-user-role-select]");
  if (!select) return;
  updateManagedUserRole(
    select.getAttribute("data-employee-id") || "",
    select.value,
    select
  );
});

documentQaReviewButton?.addEventListener("click", () => {
  trackUserEvent("document_qa_modal_opened", { selectedName });
  openDocumentQaReviewModal();
});

documentQaReviewStartButton?.addEventListener("click", () => {
  startDocumentQaReview();
});

documentQaActionCheckButton?.addEventListener("click", () => {
  checkDocumentQaActionStatus({ manual: true });
});

documentQaRevisionButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 개발/QA 보완 요청을 실행할 수 없습니다.")) return;
  requestDocumentQaRevision();
});

documentQaReviewCloseButton?.addEventListener("click", () => {
  closeDocumentQaReviewModal();
});

documentQaReviewModal?.addEventListener("click", (event) => {
  if (event.target === documentQaReviewModal) {
    closeDocumentQaReviewModal();
  }
});

documentQaReviewModal?.addEventListener("change", (event) => {
  if (event.target?.classList?.contains("document-qa-select")) {
    const card = event.target.closest(".document-qa-finding");
    if (card) {
      card.classList.toggle("is-selected", event.target.checked);
    }
    updateDocumentQaRevisionState();
  }
});

healthCheckButton?.addEventListener("click", () => {
  trackUserEvent("health_check_opened", { selectedName });
  openHealthCheckModal();
});

healthCheckStartButton?.addEventListener("click", () => {
  startHealthCheck();
});

healthCheckCloseButton?.addEventListener("click", () => {
  closeHealthCheckModal();
});

healthCheckRevisionButton?.addEventListener("click", async () => {
  if (!guardWritePermission("조회 권한은 Health Check 자동 보완을 실행할 수 없습니다.")) return;
  await startSelectedHealthCheckRevision(healthCheckRevisionButton);
});

healthCheckRecheckButton?.addEventListener("click", async () => {
  await startSelectedHealthCheckRecheck(healthCheckRecheckButton);
});

healthCheckExportButton?.addEventListener("click", async () => {
  await exportCurrentHealthCheckReport(healthCheckExportButton);
});

healthCheckArtifactRepairButton?.addEventListener("click", async () => {
  await startHealthCheckArtifactSyncRepair(healthCheckArtifactRepairButton);
});

devFormatExportButton?.addEventListener("click", () => {
  trackUserEvent("dev_format_export_opened", { selectedName });
  openDevFormatExportModal();
});

devFormatExportStartButton?.addEventListener("click", async () => {
  await startDevFormatExport();
});

devFormatExportCloseButton?.addEventListener("click", () => {
  closeDevFormatExportModal();
});

devFormatExportModal?.addEventListener("click", (event) => {
  if (event.target === devFormatExportModal) {
    closeDevFormatExportModal();
  }
});

healthCheckModal?.addEventListener("click", (event) => {
  if (event.target === healthCheckModal) {
    closeHealthCheckModal();
  }
});

healthCheckModal?.addEventListener("change", (event) => {
  if (event.target?.classList?.contains("health-check-select")) {
    const row = event.target.closest(".health-check-section-detail-row");
    row?.classList.toggle("is-selected", event.target.checked);
    if (event.target.checked) {
      setHealthCheckDetailExpanded(row, true);
    }
    updateHealthCheckRevisionState();
  }
});

alignmentCheckButton?.addEventListener("click", () => {
  trackUserEvent("analysis_alignment_check_opened", { selectedName });
  openAlignmentCheckModal();
});

alignmentCheckStartButton?.addEventListener("click", () => {
  startAlignmentCheck();
});

alignmentCheckCloseButton?.addEventListener("click", () => {
  closeAlignmentCheckModal();
});

alignmentCheckModal?.addEventListener("click", (event) => {
  if (event.target === alignmentCheckModal) {
    closeAlignmentCheckModal();
  }
});

piCheckButton?.addEventListener("click", () => {
  trackUserEvent("pi_check_opened", {});
  openPiCheckModal();
});

piCheckCloseButton?.addEventListener("click", () => {
  closePiCheckModal();
});

piCheckModal?.addEventListener("click", (event) => {
  if (event.target === piCheckModal) {
    closePiCheckModal();
  }
});

piCheckAsIsFileInput?.addEventListener("change", () => {
  updatePiCheckFileState();
});

piCheckToBeFileInput?.addEventListener("change", () => {
  updatePiCheckFileState();
});

piCheckStartButton?.addEventListener("click", () => {
  startPiCheck();
});

piCheckExportButton?.addEventListener("click", async () => {
  await exportCurrentPiCheckReport(piCheckExportButton);
});

topicConceptCloseButton?.addEventListener("click", () => {
  closeTopicConceptModal();
});

topicConceptModal?.addEventListener("click", (event) => {
  if (event.target === topicConceptModal) {
    closeTopicConceptModal();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeActiveModalFromKeyboard();
    return;
  }
  if (event.key === "Tab") {
    trapFocusInActiveModal(event);
  }
});

function activeModalBackdrop() {
  return [...document.querySelectorAll(".modal-backdrop")]
    .reverse()
    .find((modal) => !modal.hidden);
}

function focusableElementsIn(container) {
  if (!container) return [];
  return [...container.querySelectorAll('a[href], button, input, select, textarea, summary, [tabindex]:not([tabindex="-1"])')]
    .filter((element) => {
      if (element.disabled || element.hidden) return false;
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    });
}

function trapFocusInActiveModal(event) {
  const modal = activeModalBackdrop();
  if (!modal) return false;
  const focusable = focusableElementsIn(modal);
  if (!focusable.length) return false;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
    return true;
  }
  if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
    return true;
  }
  if (!modal.contains(document.activeElement)) {
    event.preventDefault();
    first.focus();
    return true;
  }
  return false;
}

function closeActiveModalFromKeyboard() {
  if (widePreviewModal && !widePreviewModal.hidden) {
    closeWidePreviewModal();
    return true;
  }
  if (topicConceptModal && !topicConceptModal.hidden) {
    closeTopicConceptModal();
    return true;
  }
  if (selectionRevisionModal && !selectionRevisionModal.hidden) {
    closeSelectionRevisionModal();
    return true;
  }
  if (diagramEditorModal && !diagramEditorModal.hidden) {
    closeDiagramEditor();
    return true;
  }
  if (editSaveModeModal && !editSaveModeModal.hidden) {
    closeEditSaveModeModal(null);
    return true;
  }
  if (fullVersionModal && !fullVersionModal.hidden) {
    closeFullVersionModal();
    return true;
  }
  if (documentQaReviewModal && !documentQaReviewModal.hidden) {
    closeDocumentQaReviewModal();
    return true;
  }
  if (healthCheckModal && !healthCheckModal.hidden) {
    closeHealthCheckModal();
    return true;
  }
  if (alignmentCheckModal && !alignmentCheckModal.hidden) {
    closeAlignmentCheckModal();
    return true;
  }
  if (channelPiArea && !channelPiArea.hidden) {
    closeChannelPiStatusModal();
    return true;
  }
  if (piCheckModal && !piCheckModal.hidden) {
    closePiCheckModal();
    return true;
  }
  if (documentAnalysisModal && !documentAnalysisModal.hidden) {
    closeDocumentAnalysisModal();
    return true;
  }
  if (serviceHealthModal && !serviceHealthModal.hidden) {
    closeServiceHealthModal();
    return true;
  }
  if (userManagementModal && !userManagementModal.hidden) {
    closeUserManagementModal();
    return true;
  }
  if (progressModal && !progressModal.hidden) {
    closeOrCancelProgressModal();
    return true;
  }
  return false;
}

documentAnalysisButton?.addEventListener("click", () => {
  trackUserEvent("document_analysis_opened", { selectedName });
  openDocumentAnalysisModal();
});

documentAnalysisCloseButton?.addEventListener("click", () => {
  closeDocumentAnalysisModal();
});

documentAnalysisModal?.addEventListener("click", (event) => {
  if (event.target === documentAnalysisModal) {
    closeDocumentAnalysisModal();
  }
});

versionSelect?.addEventListener("change", () => {
  const nextName = versionSelect.value;
  if (nextName && nextName !== selectedName) {
    selectPolicy(nextName);
  }
});

versionChangeToggle?.addEventListener("click", () => {
  toggleVersionChangeView();
});

versionChangeSummary?.addEventListener("click", (event) => {
  const target = event.target?.closest?.("[data-version-change-index]");
  if (!target) return;
  focusVersionChangeItem(Number(target.dataset.versionChangeIndex));
});

resumeDraftButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 작성 재개를 실행할 수 없습니다.")) return;
  if (selectedDraft) {
    resumeDraft(selectedDraft);
  }
});

brandHomeButton?.addEventListener("click", () => {
  goWelcomeHome();
});

sideNavToggle?.addEventListener("click", () => {
  setSideNavCollapsed(!sideNavCollapsed, { persist: true });
  trackUserEvent("side_nav_toggled", { collapsed: sideNavCollapsed });
});

workspaceAssistModeInputs.forEach((input) => {
  input.addEventListener("change", () => {
    if (!input.checked) return;
    setWorkspaceAssistEnabled(input.value === "on", { persist: true });
    trackUserEvent("workspace_assist_mode_changed", { enabled: workspaceAssistEnabled });
  });
});

workspaceAssistTabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setWorkspaceAssistTab(button.dataset.assistTab || "ai");
  });
});

form.addEventListener("change", () => {
  updateCreateAvailability();
});

topicSearch?.addEventListener("input", () => {
  renderTopicChips(topicSearch.value);
});

topicSearch?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
  }
});

topicStatusSearch?.addEventListener("input", () => {
  if (topicStatusSearch.value.trim()) {
    nextChannelTreeOpen = true;
    nextChannelTaskDefinitionTreeOpen = true;
    nextChannelRequirementsTreeOpen = true;
    nextChannelPolicyTreeOpen = true;
    storeBoolean(NEXT_CHANNEL_TREE_STORAGE_KEY, true);
    storeBoolean(NEXT_CHANNEL_TASK_DEFINITION_TREE_STORAGE_KEY, true);
    storeBoolean(NEXT_CHANNEL_REQUIREMENTS_TREE_STORAGE_KEY, true);
    storeBoolean(NEXT_CHANNEL_POLICY_TREE_STORAGE_KEY, true);
  }
  renderPolicyTopicList();
});

topicStatusSearch?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
  }
});

topicSelect?.addEventListener("change", () => {
  if (rewriteRequestTopic && !isRewriteRequestForTopic(topicSelect.value)) {
    rewriteRequestTopic = "";
  }
  trackUserEvent("topic_selected_for_request", { topic: topicSelect.value });
  updateRequestTopicSummary(topicSelect.value);
  renderRequestTopicDirection(topicSelect.value);
  renderTopicChips(topicSearch?.value || "");
  renderPolicyTopicList();
});

briefInput?.addEventListener("input", () => {
  if (briefInput.value !== lastAutoBrief) {
    lastAutoBrief = "";
  }
});

editButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 직접 편집을 실행할 수 없습니다.")) return;
  trackUserEvent("manual_edit_started", { selectedName, analysisReferenceId: selectedAnalysisReferenceId });
  enterEditMode();
});

deleteSelectedButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 문서 삭제를 실행할 수 없습니다.")) return;
  if (selectedName) {
    deletePolicy(selectedName);
    return;
  }
  if (selectedDraft) {
    deleteDraft(selectedDraft);
  }
});

completionStatusButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 작성 상태 변경을 실행할 수 없습니다.")) return;
  togglePolicyCompletion();
});

cancelEditButton?.addEventListener("click", () => {
  trackUserEvent("manual_edit_canceled", { selectedName, analysisReferenceId: selectedAnalysisReferenceId });
  exitEditMode(true);
});

saveEditButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 문서 저장을 실행할 수 없습니다.")) return;
  saveEditedPolicy();
});

editorToolButtons.forEach((button) => {
  button.addEventListener("mousedown", (event) => {
    event.preventDefault();
  });
  button.addEventListener("click", () => {
    runEditorCommand(button.dataset.editorCommand || "");
  });
});

editorFontSizeSelect?.addEventListener("mousedown", (event) => {
  event.stopPropagation();
});

editorFontSizeSelect?.addEventListener("change", () => {
  applyEditorFontSize(editorFontSizeSelect.value);
  editorFontSizeSelect.value = "";
});

editorBulletStyleSelect?.addEventListener("mousedown", (event) => {
  event.stopPropagation();
});

editorBulletStyleSelect?.addEventListener("change", () => {
  applyEditorBulletStyle(editorBulletStyleSelect.value);
  editorBulletStyleSelect.value = "";
});

editorCommentSubmitButton?.addEventListener("click", () => {
  submitEditorComment();
});

editorCommentInput?.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    submitEditorComment();
  }
});

editorCommentSearchInput?.addEventListener("input", () => {
  editorCommentSearchQuery = String(editorCommentSearchInput.value || "");
  renderEditorCommentList();
});

editorCommentStatusFilterInputs.forEach((input) => {
  input.addEventListener("change", () => {
    editorCommentStatusFilterValues = new Set(
      editorCommentStatusFilterInputs
        .filter((candidate) => candidate.checked)
        .map((candidate) => candidate.value)
    );
    renderEditorCommentList();
  });
});

editorCommentSortButtons.forEach((button) => {
  button.addEventListener("click", () => {
    editorCommentSortOrder = button.dataset.commentSort === "oldest" ? "oldest" : "recent";
    if (editorCommentSortMenu) editorCommentSortMenu.open = false;
    renderEditorCommentList();
  });
});

document.addEventListener("click", (event) => {
  if (event.target.closest(".editor-comment-action-menu")) return;
  closeEditorCommentActionMenus();
  if (selectedEditorCommentId && !event.target.closest(".editor-comment-item")) {
    selectedEditorCommentId = "";
    renderEditorCommentList();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeEditorCommentActionMenus();
    if (selectedEditorCommentId) {
      selectedEditorCommentId = "";
      renderEditorCommentList();
    }
  }
});

diagramEditorTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    setDiagramEditorTab(tab.dataset.diagramTab || "usecase");
  });
});

diagramEditorCloseButton?.addEventListener("click", () => {
  closeDiagramEditor();
});

diagramEditorCancelButton?.addEventListener("click", () => {
  closeDiagramEditor();
});

diagramEditorModal?.addEventListener("click", (event) => {
  if (event.target === diagramEditorModal) closeDiagramEditor();
});

diagramEditorSaveButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 다이어그램 저장을 실행할 수 없습니다.")) return;
  saveDiagramEditor();
});

revisionButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 Agent 수정 요청을 실행할 수 없습니다.")) return;
  trackUserEvent("revision_button_clicked", {
    selectedName,
    selectedDraft: Boolean(selectedDraft),
    instructionChars: revisionRequest?.value?.trim()?.length || 0,
  });
  requestAgentRevision();
});

previewFrame?.addEventListener("load", () => {
  hideSelectionRevisionButton();
  hidePreviewFrameScrollbars();
  enhancePreviewDocumentForSandbox();
  bindPreviewExternalLinks();
  resizePreviewFrameToContent();
  window.setTimeout(resizePreviewFrameToContent, 120);
  window.setTimeout(resizePreviewFrameToContent, 600);
  bindPreviewBpmnDownloads();
  installPreviewSelectionHandlers();
  updateEditorToolbarState();
  updateWorkspaceAssistPanel();
  applyEditorCommentHighlights();
  applyVersionChangeAnnotationsToPreview();
  if (widePreviewModal && !widePreviewModal.hidden && !isEditing) {
    syncWidePreviewFromCurrentFrame();
  }
});

window.addEventListener("resize", () => {
  hideSelectionRevisionButton();
  resizePreviewFrameToContent();
});

selectionInlineAiButton?.addEventListener("click", () => {
  requestInlineSelectedRevision();
});

selectionInlineCommentButton?.addEventListener("click", () => {
  addInlineSelectionComment();
});

selectionInlineRequest?.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    requestInlineSelectedRevision();
  }
});

selectionRevisionCloseButton?.addEventListener("click", () => {
  closeSelectionRevisionModal();
});

widePreviewButton?.addEventListener("click", () => {
  openWidePreviewModal();
});

widePreviewCloseButton?.addEventListener("click", () => {
  closeWidePreviewModal();
});

widePreviewModal?.addEventListener("click", (event) => {
  if (event.target === widePreviewModal) {
    closeWidePreviewModal();
  }
});

widePreviewFrame?.addEventListener("load", () => {
  try {
    applyWidePreviewResponsiveLayout(widePreviewFrame.contentDocument);
    widePreviewFrame.contentWindow?.scrollTo(0, 0);
  } catch (_error) {
    // Ignore cross-frame scroll reset errors and rely on the browser default.
  }
});

selectionRevisionCancelButton?.addEventListener("click", () => {
  closeSelectionRevisionModal();
});

selectionRevisionSubmitButton?.addEventListener("click", () => {
  if (!guardWritePermission("조회 권한은 선택 영역 수정을 실행할 수 없습니다.")) return;
  requestSelectedRevision();
});

selectionRevisionRequest?.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    if (!guardWritePermission("조회 권한은 선택 영역 수정을 실행할 수 없습니다.")) return;
    requestSelectedRevision();
  }
});

selectionRevisionModeInputs.forEach((input) => {
  input.addEventListener("change", () => {
    updateSelectionRevisionSubmitLabel();
  });
});

editSaveModeModal?.addEventListener("click", (event) => {
  if (event.target === editSaveModeModal) {
    closeEditSaveModeModal(null);
  }
});

editSaveModeCloseButton?.addEventListener("click", () => {
  closeEditSaveModeModal(null);
});

editSaveModeCloseButton?.addEventListener("mousedown", (event) => {
  event.preventDefault();
  closeEditSaveModeModal(null);
});

editSaveModeCancelButton?.addEventListener("click", () => {
  closeEditSaveModeModal(null);
});

editSaveModeCancelButton?.addEventListener("mousedown", (event) => {
  event.preventDefault();
  closeEditSaveModeModal(null);
});

document.addEventListener("pointerdown", (event) => {
  if (event.target?.closest?.("#editSaveModeCloseButton, #editSaveModeCancelButton")) {
    event.preventDefault();
    closeEditSaveModeModal(null);
  }
}, true);

document.addEventListener("click", (event) => {
  if (event.target?.closest?.("#editSaveModeCloseButton, #editSaveModeCancelButton")) {
    event.preventDefault();
    closeEditSaveModeModal(null);
  }
}, true);

editSaveModeNewVersionButton?.addEventListener("click", () => {
  resolveEditSaveMode("new_version");
});

editSaveModeOverwriteButton?.addEventListener("click", () => {
  resolveEditSaveMode("overwrite");
});

manualContinueButton?.addEventListener("click", () => {
  submitManualReview("continue");
});

manualReviseButton?.addEventListener("click", () => {
  submitManualReview(manualReviseButton.dataset.action || "revise");
});

async function loadPolicies(preferredName = "", options = {}) {
  const response = await fetch(apiPath("/api/policies"));
  const data = await response.json();
  currentItems = data.items || [];
  currentDrafts = data.drafts || [];
  cacheDevQaReports(currentItems);
  cacheHealthCheckReports(currentItems);
  if (policyCount) {
    policyCount.textContent = `${currentItems.length}건`;
  }
  renderDashboardPolicyStatus();
  loadDashboard();
  renderList();
  renderPolicyTopicList();
  updateCreateAvailability();
  if (options.autoSelect === false) {
    return;
  }

  const nextItem =
    currentItems.find((item) => item.name === preferredName) ||
    currentItems.find((item) => item.name === selectedName);

  if (nextItem) {
    selectPolicy(nextItem.name);
  } else if (selectedDraft) {
    const draft = latestDraftForTopic(selectedDraft.topic);
    if (draft) {
      selectDraft(draft);
    } else {
      clearPreview();
    }
  } else if (preferredName || selectedName) {
    clearPreview();
  } else if (activeMainWorkspace === "welcome") {
    showWelcomeWorkspace();
  }
}

function updateCreateAvailability() {
  updateTemplateTypeAccess();
  const formData = new FormData(form);
  const topic = getCurrentRequestTopic(formData);
  const exists = currentItems.some((item) => normalizeTopic(item.topic) === normalizeTopic(topic));
  const draft = latestDraftForTopic(topic);
  const rewrite = isRewriteRequestForTopic(topic);
  const fullTemplateRequested = formData.get("templateType") === "full";
  const writeAllowed = canCurrentUserWritePolicies();
  const adminActionBlocked = (rewrite || fullTemplateRequested) && !canCurrentUserRunAdminPolicyActions();
  setSubmitButtonsDisabled(!writeAllowed || adminActionBlocked || (exists && !rewrite) || draft || progressTimer);
  if (!writeAllowed && currentUser) {
    setMessage("조회 권한은 문서 생성·수정·삭제 없이 조회, 다운로드, 검수, Health Check만 이용할 수 있습니다.");
  } else if (adminActionBlocked && rewrite) {
    setMessage("정책서 다시 작성은 관리자만 실행할 수 있습니다.");
  } else if (adminActionBlocked && fullTemplateRequested) {
    setMessage("Full 버전 작성은 관리자만 실행할 수 있습니다.");
  } else if (exists && rewrite) {
    setMessage("기존 문서는 보존하고 새 버전으로 다시 작성합니다. 작성 옵션을 확인한 뒤 시작해 주세요.");
  } else if (exists) {
    setMessage("이미 같은 주제로 생성된 정책서가 있습니다. 신규 생성 대신 오른쪽 미리보기에서 편집하거나 Agent에게 수정 요청해 주세요.");
  } else if (draft) {
    setMessage("작성 중단된 초안이 있습니다. 문서 작업실에서 '이어서 작성하기'를 눌러 계속 진행해 주세요.");
  } else if (!progressTimer && !message.classList.contains("error")) {
    setMessage("");
  }
}

function isRewriteRequestForTopic(topic = "") {
  return Boolean(rewriteRequestTopic) && normalizeTopic(rewriteRequestTopic) === normalizeTopic(topic);
}

function clearRewriteRequest() {
  rewriteRequestTopic = "";
  updateRequestTopicSummary(topicSelect?.value || "");
  updateCreateAvailability();
}

function startRewriteRequestFromSelectedPolicy() {
  if (!guardWritePermission("조회 권한은 다시 작성을 실행할 수 없습니다.")) return;
  if (!guardPolicyAdminAction("정책서 다시 작성은 관리자만 실행할 수 있습니다.")) return;
  const item = selectedPolicyItem();
  if (!item || isEditing) return;
  rewriteRequestTopic = item.topic;
  selectedName = "";
  selectedDraft = null;
  selectedAnalysisReferenceId = "";
  selectedTaskDefinitionId = "";
  exitEditMode(false);
  setTopicSelectValue(item.topic, { dispatch: true });
  setTemplateType(item.templateType || (item.templateLabel === "Full" ? "full" : "simple"));
  updateRequestTopicSummary(getCurrentRequestTopic() || item.topic);
  showRequestWorkspace();
  clearPreview(false);
  renderList();
  renderPolicyTopicList();
  renderTopicChips(topicSearch?.value || "");
  updateCreateAvailability();
  focusWorkspaceOnCompact(requestArea);
  trackUserEvent("policy_rewrite_requested_from_workspace", {
    name: item.name,
    topic: item.topic,
    version: item.version || "",
  });
}

function setTemplateType(templateType = "simple") {
  const normalized = templateType === "full" && canCurrentUserRunAdminPolicyActions() ? "full" : "simple";
  const input = form?.querySelector(`input[name="templateType"][value="${normalized}"]`);
  if (input) input.checked = true;
  updateTemplateTypeAccess();
}

function renderPolicyTopicList() {
  if (!policyTopicList) return;
  const topics = getTopicOptions();
  const normalizedQuery = normalizeTopic(topicStatusSearch?.value || "");
  const requirementTopics = normalizedQuery
    ? topics.filter((topic) => normalizeTopic(topic).includes(normalizedQuery))
    : topics;
  const requirementChildrenHtml = renderRequirementTopicRows(
    requirementTopics,
    normalizedQuery ? "검색 조건에 맞는 요구사항 주제가 없습니다." : "등록된 요구사항 주제가 없습니다."
  );
  const requirementVisibleCount = requirementTopicTreeCountLabel(requirementTopics);
  if (topics.length === 0) {
    policyTopicList.innerHTML = renderPolicyTopicTreeGroups(
      '<div class="topic-status-empty">등록된 정책서 주제가 없습니다.</div>',
      0,
      requirementChildrenHtml,
      requirementVisibleCount
    );
    bindPolicyTopicTreeToggles();
    return;
  }

  const rows = topics
    .map((topic) => {
      const item = latestItemForTopic(topic);
      const draft = item ? null : latestDraftForTopic(topic);
      const status = policyTopicStatus(item, draft);
      return { topic, item, draft, status };
    })
    .filter(({ topic, item, draft, status }) => {
      if (!normalizedQuery) return true;
      const searchableText = [
        topic,
        status.text,
        status.label,
        item?.version || "",
        draft?.stageLabel || "",
      ].join(" ");
      return normalizeTopic(searchableText).includes(normalizedQuery);
    });

  if (rows.length === 0) {
    policyTopicList.innerHTML = renderPolicyTopicTreeGroups(
      '<div class="topic-status-empty">검색 조건에 맞는 정책서 주제가 없습니다.</div>',
      0,
      requirementChildrenHtml,
      requirementVisibleCount
    );
    bindPolicyTopicTreeToggles();
    return;
  }

  const rowHtml = rows
    .map((row) => {
      const { topic, item, draft, status } = row;
      const active = item?.name === selectedName || (!item && draft && selectedDraft?.id === draft.id) || (!item && !draft && normalizeTopic(topicSelect?.value || "") === normalizeTopic(topic));
      const statusText = item ? `${status.text} · ${item.version}${item.specSync?.needed ? " · Spec" : ""}` : status.text;
      return `
        <button class="topic-status-row ${active ? "active" : ""}" type="button" data-topic="${escapeHtml(topic)}" data-policy="${escapeHtml(item?.name || "")}" data-draft="${escapeHtml(draft?.id || "")}">
          <span class="topic-status-main">
            <strong>${escapeHtml(topic)}</strong>
          </span>
          <span class="topic-status-badge ${escapeHtml(status.className)}">${escapeHtml(statusText)}</span>
        </button>
      `;
    })
    .join("");
  policyTopicList.innerHTML = renderPolicyTopicTreeGroups(rowHtml, rows.length, requirementChildrenHtml, requirementVisibleCount);
  bindPolicyTopicTreeToggles();

  policyTopicList.querySelectorAll(".topic-status-row").forEach((button) => {
    button.addEventListener("click", () => {
      const policyName = button.dataset.policy || "";
      const topic = button.dataset.topic || "";
      if (policyName) {
        selectPolicy(policyName);
        return;
      }
      const draftId = button.dataset.draft || "";
      if (draftId) {
        const draft = currentDrafts.find((candidate) => candidate.id === draftId);
        if (draft) {
          selectDraft(draft);
          return;
        }
      }
      if (topic) {
        selectUnwrittenTopic(topic);
      }
    });
  });
}

function renderPolicyTopicTreeGroups(channelChildrenHtml, channelVisibleCount, requirementChildrenHtml = "", requirementVisibleCount = 0) {
  const analysisChildrenHtml = renderAnalysisReferenceRows();
  const taskDefinitionChildrenHtml = renderTaskDefinitionReferenceRows();
  const nextChannelChildrenHtml = [
    renderTopicTreeGroup({
      key: "next-channel-analysis",
      title: "현황 분석",
      count: ANALYSIS_REFERENCES.length,
      isOpen: nextChannelAnalysisTreeOpen,
      childrenHtml: analysisChildrenHtml,
      className: "topic-tree-nested",
    }),
    renderTopicTreeGroup({
      key: "next-channel-task-definition",
      title: "과제 정의",
      count: TASK_DEFINITION_REFERENCES.length,
      isOpen: nextChannelTaskDefinitionTreeOpen,
      childrenHtml: taskDefinitionChildrenHtml,
      className: "topic-tree-nested",
    }),
    renderTopicTreeGroup({
      key: "next-channel-requirements",
      title: "요구사항",
      count: requirementVisibleCount,
      isOpen: nextChannelRequirementsTreeOpen,
      childrenHtml: requirementChildrenHtml || '<div class="topic-status-empty">등록된 요구사항 주제가 없습니다.</div>',
      className: "topic-tree-nested",
    }),
    renderTopicTreeGroup({
      key: "next-channel-policy",
      title: "정책서",
      count: channelVisibleCount,
      isOpen: nextChannelPolicyTreeOpen,
      childrenHtml: channelChildrenHtml,
      className: "topic-tree-nested",
    }),
  ].join("");
  return [
    renderTopicTreeGroup({
      key: "next-bss",
      title: "Next BSS",
      count: 0,
      isOpen: nextBssTreeOpen,
      childrenHtml: '<div class="topic-status-empty topic-tree-coming-soon">지원 예정입니다.</div>',
      className: "topic-tree-root",
    }),
    renderTopicTreeGroup({
      key: "next-channel",
      title: "Next Channel",
      count: 4,
      isOpen: nextChannelTreeOpen,
      childrenHtml: nextChannelChildrenHtml,
      className: "topic-tree-root",
    }),
  ].join("");
}

function renderAnalysisReferenceRows() {
  return ANALYSIS_REFERENCES
    .map((reference) => {
      if (Array.isArray(reference.children) && reference.children.length) {
        const isFunctionInventoryGroup = reference.id === "function-inventory";
        const isVocGroup = reference.id === "voc-analysis";
        return renderTopicTreeGroup({
          key: `analysis-${reference.id}`,
          title: reference.title,
          count: reference.children.length,
          isOpen: isFunctionInventoryGroup
            ? nextChannelFunctionInventoryTreeOpen
            : isVocGroup
              ? nextChannelVocAnalysisTreeOpen
              : false,
          childrenHtml: renderAnalysisChildReferenceRows(reference.children),
          className: "topic-tree-nested topic-tree-subnested",
        });
      }
      const rowContent = `
        <span class="topic-status-main">
          <strong>${escapeHtml(reference.title)}</strong>
        </span>
      `;
      if (reference.url) {
        return `
          <button class="topic-reference-row topic-analysis-row ${reference.id === selectedAnalysisReferenceId ? "active" : ""}" type="button" data-analysis-reference-id="${escapeHtml(reference.id)}">
            ${rowContent}
          </button>
        `;
      }
      return `
        <div class="topic-reference-row topic-analysis-row topic-analysis-row-static" data-analysis-reference-id="${escapeHtml(reference.id)}" role="listitem">
          ${rowContent}
        </div>
      `;
    })
    .join("");
}

function renderAnalysisChildReferenceRows(references = []) {
  return references
    .map((reference) => {
      const rowContent = `
        <span class="topic-status-main">
          <strong>${escapeHtml(reference.title)}</strong>
        </span>
      `;
      if (reference.url) {
        return `
          <button class="topic-reference-row topic-analysis-row topic-analysis-child-row ${reference.id === selectedAnalysisReferenceId ? "active" : ""}" type="button" data-analysis-reference-id="${escapeHtml(reference.id)}">
            ${rowContent}
          </button>
        `;
      }
      return `
        <div class="topic-reference-row topic-analysis-row topic-analysis-row-static topic-analysis-child-row" data-analysis-reference-id="${escapeHtml(reference.id)}" role="listitem">
          ${rowContent}
        </div>
      `;
    })
    .join("");
}

function renderTaskDefinitionReferenceRows() {
  return TASK_DEFINITION_REFERENCES
    .map((reference) => {
      return `
        <button class="topic-reference-row ${reference.id === selectedTaskDefinitionId ? "active" : ""}" type="button" data-task-definition-id="${escapeHtml(reference.id)}">
          <span class="topic-status-main">
            <strong>${escapeHtml(reference.title)}</strong>
          </span>
        </button>
      `;
    })
    .join("");
}

function renderRequirementTopicRows(topics = [], emptyText = "등록된 요구사항 주제가 없습니다.") {
  if (!topics.length) {
    return `<div class="topic-status-empty">${escapeHtml(emptyText)}</div>`;
  }
  return topics
    .map((topic) => `
      <button class="topic-requirement-row ${normalizeTopic(topic) === normalizeTopic(selectedRequirementTopic) ? "active" : ""}" type="button" data-requirement-topic="${escapeHtml(topic)}">
        <span class="topic-status-main">
          <strong>${escapeHtml(topic)}</strong>
        </span>
        <span class="topic-status-badge requirement-count">${escapeHtml(requirementTopicCountBadgeLabel(topic))}</span>
      </button>
    `)
    .join("");
}

function requirementTopicCountEntry(topic = "") {
  return requirementTopicCounts[normalizeTopic(topic)] || null;
}

function detailRequirementCountForTopic(topic = "") {
  const entry = requirementTopicCountEntry(topic);
  return Number(entry?.detailRequirementCount || 0);
}

function requirementTopicCountBadgeLabel(topic = "") {
  if (!requirementTopicCountsLoaded) return "...";
  return detailRequirementCountForTopic(topic).toLocaleString("ko-KR");
}

function requirementTopicTreeCountLabel(topics = []) {
  if (!requirementTopicCountsLoaded) return "...";
  return topics
    .reduce((total, topic) => total + detailRequirementCountForTopic(topic), 0)
    .toLocaleString("ko-KR");
}

function renderTopicTreeLeaf({ title, count }) {
  return `
    <div class="topic-tree-group topic-tree-leaf">
      <div class="topic-tree-toggle" aria-label="${escapeHtml(title)}">
        <span class="topic-tree-caret" aria-hidden="true"></span>
        <span class="topic-tree-folder" aria-hidden="true"></span>
        <span class="topic-tree-title">${escapeHtml(title)}</span>
        <span class="topic-tree-count">${escapeHtml(String(count))}</span>
      </div>
    </div>
  `;
}

function renderTopicTreeGroup({ key, title, count, isOpen, childrenHtml, className = "" }) {
  return `
    <div class="topic-tree-group ${className} ${isOpen ? "open" : "closed"}" data-tree-key="${escapeHtml(key)}">
      <button class="topic-tree-toggle" type="button" aria-expanded="${isOpen ? "true" : "false"}" data-tree-toggle="${escapeHtml(key)}">
        <span class="topic-tree-caret" aria-hidden="true"></span>
        <span class="topic-tree-folder" aria-hidden="true"></span>
        <span class="topic-tree-title">${escapeHtml(title)}</span>
        <span class="topic-tree-count">${escapeHtml(String(count))}</span>
      </button>
      <div class="topic-tree-children" ${isOpen ? "" : "hidden"}>
        ${childrenHtml}
      </div>
    </div>
  `;
}

function bindPolicyTopicTreeToggles() {
  policyTopicList?.querySelectorAll("[data-tree-toggle]").forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const key = toggle.dataset.treeToggle || "";
      if (key === "next-channel") {
        nextChannelTreeOpen = !nextChannelTreeOpen;
        storeBoolean(NEXT_CHANNEL_TREE_STORAGE_KEY, nextChannelTreeOpen);
      } else if (key === "next-channel-analysis") {
        nextChannelAnalysisTreeOpen = !nextChannelAnalysisTreeOpen;
        storeBoolean(NEXT_CHANNEL_ANALYSIS_TREE_STORAGE_KEY, nextChannelAnalysisTreeOpen);
      } else if (key === "analysis-function-inventory") {
        nextChannelFunctionInventoryTreeOpen = !nextChannelFunctionInventoryTreeOpen;
        storeBoolean(NEXT_CHANNEL_FUNCTION_INVENTORY_TREE_STORAGE_KEY, nextChannelFunctionInventoryTreeOpen);
      } else if (key === "analysis-voc-analysis") {
        nextChannelVocAnalysisTreeOpen = !nextChannelVocAnalysisTreeOpen;
        storeBoolean(NEXT_CHANNEL_VOC_ANALYSIS_TREE_STORAGE_KEY, nextChannelVocAnalysisTreeOpen);
      } else if (key === "next-channel-task-definition") {
        nextChannelTaskDefinitionTreeOpen = !nextChannelTaskDefinitionTreeOpen;
        storeBoolean(NEXT_CHANNEL_TASK_DEFINITION_TREE_STORAGE_KEY, nextChannelTaskDefinitionTreeOpen);
      } else if (key === "next-channel-requirements") {
        nextChannelRequirementsTreeOpen = !nextChannelRequirementsTreeOpen;
        storeBoolean(NEXT_CHANNEL_REQUIREMENTS_TREE_STORAGE_KEY, nextChannelRequirementsTreeOpen);
      } else if (key === "next-channel-policy") {
        nextChannelPolicyTreeOpen = !nextChannelPolicyTreeOpen;
        storeBoolean(NEXT_CHANNEL_POLICY_TREE_STORAGE_KEY, nextChannelPolicyTreeOpen);
      } else if (key === "next-bss") {
        nextBssTreeOpen = !nextBssTreeOpen;
        storeBoolean(NEXT_BSS_TREE_STORAGE_KEY, nextBssTreeOpen);
      }
      renderPolicyTopicList();
    });
  });
  policyTopicList?.querySelectorAll("[data-task-definition-id]").forEach((button) => {
    button.addEventListener("click", () => {
      selectTaskDefinitionReference(button.dataset.taskDefinitionId || "");
    });
  });
  policyTopicList?.querySelectorAll("button[data-analysis-reference-id]").forEach((button) => {
    button.addEventListener("click", () => {
      selectAnalysisReference(button.dataset.analysisReferenceId || "");
    });
  });
  policyTopicList?.querySelectorAll("[data-requirement-topic]").forEach((button) => {
    button.addEventListener("click", () => {
      selectRequirementTopic(button.dataset.requirementTopic || "");
    });
  });
}

function analysisReferenceById(id = "") {
  for (const reference of ANALYSIS_REFERENCES) {
    if (reference.id === id) return reference;
    const child = Array.isArray(reference.children)
      ? reference.children.find((item) => item.id === id)
      : null;
    if (child) return child;
  }
  return null;
}

function selectedAnalysisReference() {
  return selectedAnalysisReferenceId ? analysisReferenceById(selectedAnalysisReferenceId) : null;
}

function analysisReferenceFileName(reference = selectedAnalysisReference()) {
  const rawUrl = String(reference?.url || "").trim();
  if (!rawUrl) return "analysis-reference.html";
  try {
    const url = new URL(rawUrl, window.location.origin);
    const name = decodeURIComponent(url.pathname.split("/").filter(Boolean).pop() || "");
    return name || `${reference?.id || "analysis-reference"}.html`;
  } catch (_error) {
    const name = rawUrl.split("?")[0].split("/").filter(Boolean).pop() || "";
    return name || `${reference?.id || "analysis-reference"}.html`;
  }
}

function hasAnalysisReferenceSelection() {
  return Boolean(selectedAnalysisReferenceId && selectedAnalysisReference()?.url && !selectedName && !selectedDraft);
}

function taskDefinitionReferenceById(id = "") {
  return TASK_DEFINITION_REFERENCES.find((reference) => reference.id === id) || null;
}

function clearPreviewInlineDocument() {
  previewFrame?.removeAttribute("srcdoc");
}

function cacheBustedReferenceUrl(url = "") {
  if (!url) return "";
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}v=${Date.now().toString(36)}`;
}

function selectAnalysisReference(id = "") {
  const reference = analysisReferenceById(id);
  if (!reference || !reference.url) return;
  const previewUrl = cacheBustedReferenceUrl(reference.url);
  selectedAnalysisReferenceId = reference.id;
  selectedTaskDefinitionId = "";
  selectedRequirementTopic = "";
  selectedName = "";
  selectedDraft = null;
  latestQaReviewReport = null;
  latestHealthCheckReport = null;
  editorComments = [];
  editorSuggestions = [];
  selectedEditorContext = null;
  selectedEditorCommentId = "";
  clearVersionChangeView();
  hideSelectionRevisionButton();
  closeSelectionRevisionModal();
  exitEditMode(false);
  showDocumentWorkspace();
  hideWorkspaceAssistPanel();
  renderWorkspaceTopicDirection("");
  resetPreviewFrameHeight();
  clearPreviewInlineDocument();
  previewFrame.src = previewUrl;
  originalPreviewUrl = previewUrl;
  previewTitle.textContent = "현황 분석";
  previewMeta.textContent = reference.title;
  openLink.href = previewUrl;
  setDownloadLink(previewUrl, `${reference.id}.html`);
  setJsonDownloadLink("", "");
  if (versionSelect) versionSelect.innerHTML = "";
  if (versionSelectWrap) versionSelectWrap.hidden = true;
  revisionPanel.hidden = true;
  setPreviewActionMode("analysis-reference");
  updatePreviewMoreActionsVisibility();
  renderList();
  renderPolicyTopicList();
  setMessage(`${reference.title} 설명형 HTML을 미리보기로 열었습니다.`);
  focusWorkspaceOnCompact(resultArea);
}

function selectTaskDefinitionReference(id = "") {
  const reference = taskDefinitionReferenceById(id);
  if (!reference) return;
  selectedAnalysisReferenceId = "";
  selectedTaskDefinitionId = reference.id;
  selectedRequirementTopic = "";
  selectedName = "";
  selectedDraft = null;
  latestQaReviewReport = null;
  latestHealthCheckReport = null;
  editorComments = [];
  editorSuggestions = [];
  selectedEditorContext = null;
  selectedEditorCommentId = "";
  clearVersionChangeView();
  hideSelectionRevisionButton();
  closeSelectionRevisionModal();
  exitEditMode(false);
  showDocumentWorkspace();
  hideWorkspaceAssistPanel();
  renderWorkspaceTopicDirection("");
  resetPreviewFrameHeight();
  clearPreviewInlineDocument();
  previewFrame.src = reference.url;
  originalPreviewUrl = reference.url;
  previewTitle.textContent = "과제 정의";
  previewMeta.textContent = reference.title;
  openLink.href = reference.url;
  setDownloadLink(reference.url, `${reference.id}.html`);
  setJsonDownloadLink("", "");
  if (versionSelect) versionSelect.innerHTML = "";
  if (versionSelectWrap) versionSelectWrap.hidden = true;
  revisionPanel.hidden = true;
  setPreviewActionMode("empty");
  updatePreviewMoreActionsVisibility();
  renderList();
  renderPolicyTopicList();
  setMessage(reference.status === "completed" ? "과제 정의 설명형 HTML을 미리보기로 열었습니다." : "TK task로 등록된 분석 대기 문서입니다.");
  focusWorkspaceOnCompact(resultArea);
}

async function selectRequirementTopic(topic = "") {
  const selectedTopic = String(topic || "").trim();
  if (!selectedTopic) return;
  selectedRequirementTopic = selectedTopic;
  selectedAnalysisReferenceId = "";
  selectedTaskDefinitionId = "";
  selectedName = "";
  selectedDraft = null;
  latestQaReviewReport = null;
  latestHealthCheckReport = null;
  editorComments = [];
  editorSuggestions = [];
  selectedEditorContext = null;
  selectedEditorCommentId = "";
  clearVersionChangeView();
  clearEditorCommentHighlights();
  hideSelectionRevisionButton();
  closeSelectionRevisionModal();
  exitEditMode(false);
  showDocumentWorkspace();
  hideWorkspaceAssistPanel();
  renderWorkspaceTopicDirection("");
  resetPreviewFrameHeight();
  clearPreviewInlineDocument();
  previewFrame.removeAttribute("src");
  originalPreviewUrl = "";
  previewTitle.textContent = `${selectedTopic} 요구사항`;
  previewMeta.textContent = "상위 요구사항을 조회하고 있습니다.";
  openLink.href = "#";
  setDownloadLink("", "");
  setJsonDownloadLink("", "");
  if (versionSelect) versionSelect.innerHTML = "";
  if (versionSelectWrap) versionSelectWrap.hidden = true;
  revisionPanel.hidden = true;
  setPreviewActionMode("empty");
  renderPolicyTopicList();
  focusWorkspaceOnCompact(resultArea);

  previewFrame.srcdoc = renderRequirementsPreviewDocument({
    topic: selectedTopic,
    rows: [],
    requirementCount: 0,
    detailRequirementCount: 0,
    loading: true,
  });

  try {
    const response = await fetch(apiPath(`/api/requirements?topic=${encodeURIComponent(selectedTopic)}`));
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "요구사항을 불러오지 못했습니다.");
    }
    if (normalizeTopic(selectedRequirementTopic) !== normalizeTopic(selectedTopic)) return;
    previewMeta.textContent = `상위 요구사항 ${Number(data.requirementCount || 0).toLocaleString("ko-KR")}건 · 상세 요구사항 ${Number(data.detailRequirementCount || 0).toLocaleString("ko-KR")}건`;
    previewFrame.srcdoc = renderRequirementsPreviewDocument({
      topic: selectedTopic,
      rows: Array.isArray(data.rows) ? data.rows : [],
      requirementCount: Number(data.requirementCount || 0),
      detailRequirementCount: Number(data.detailRequirementCount || 0),
    });
    setMessage(`${selectedTopic} 요구사항을 조회했습니다.`);
  } catch (error) {
    if (normalizeTopic(selectedRequirementTopic) !== normalizeTopic(selectedTopic)) return;
    previewMeta.textContent = "요구사항 조회 오류";
    previewFrame.srcdoc = renderRequirementsPreviewDocument({
      topic: selectedTopic,
      rows: [],
      requirementCount: 0,
      detailRequirementCount: 0,
      error: error.message,
    });
    setMessage(error.message, true);
  }
}

function formatRequirementCell(value = "") {
  return escapeHtml(value).replace(/\r?\n/g, "<br/>");
}

function renderRequirementsPreviewDocument({ topic = "", rows = [], requirementCount = 0, detailRequirementCount = 0, loading = false, error = "" } = {}) {
  const safeTopic = escapeHtml(topic || "요구사항");
  const bodyRows = rows.length
    ? rows.map((row) => `
        <tr>
          <td class="id-cell">${formatRequirementCell(row.detail_id || row.requirement_id || "-")}</td>
          <td class="name-cell">${formatRequirementCell(row.detail_name || row.requirement_name || "-")}</td>
          <td class="description-cell">${formatRequirementCell(row.detail_description || row.requirement_description || "-")}</td>
          <td>${formatRequirementCell(row.requirement_type || "-")}</td>
          <td>${formatRequirementCell(row.priority || "-")}</td>
          <td>${formatRequirementCell(row.source || "-")}</td>
          <td class="mapping-cell">${formatRequirementCell(row.policy_mapping_status || "-")}</td>
        </tr>
      `).join("")
    : `<tr><td class="empty-cell" colspan="7">${escapeHtml(loading ? "요구사항을 불러오고 있습니다." : error || "표시할 요구사항이 없습니다.")}</td></tr>`;
  return `<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>${safeTopic} 요구사항</title>
  <style>
    :root { --ink:#172033; --soft:#56657a; --muted:#8793a5; --line:#dfe8f3; --blue:#2563eb; --bg:#f5f7fb; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; line-height:1.58; }
    main { width:calc(100% - 24px); margin:0 auto; padding:20px 0 36px; }
    .panel { overflow:hidden; border:1px solid var(--line); border-radius:22px; background:#fff; box-shadow:0 18px 44px rgba(31,36,48,.08); }
    .table-wrap { overflow-x:auto; overflow-y:visible; }
    table { width:100%; min-width:1500px; border-collapse:separate; border-spacing:0; table-layout:fixed; }
    th, td { border-bottom:1px solid var(--line); border-right:1px solid var(--line); padding:13px 14px; vertical-align:top; text-align:left; font-size:13px; word-break:keep-all; overflow-wrap:anywhere; }
    th:last-child, td:last-child { border-right:0; }
    th { position:sticky; top:0; z-index:1; background:#f1f6ff; color:#1f2a44; font-size:12px; font-weight:950; letter-spacing:.02em; }
    td { background:#fff; }
    tbody tr:nth-child(even) td { background:#fbfdff; }
    .id-cell { color:#1d4ed8; font-weight:900; white-space:nowrap; }
    .name-cell { font-weight:850; }
    .description-cell { line-height:1.62; }
    .mapping-cell { color:#334155; font-size:12px; line-height:1.55; }
    .empty-cell { padding:44px 18px; color:var(--muted); text-align:center; font-weight:850; }
    col:nth-child(1) { width:150px; }
    col:nth-child(2) { width:240px; }
    col:nth-child(3) { width:430px; }
    col:nth-child(4) { width:120px; }
    col:nth-child(5) { width:110px; }
    col:nth-child(6) { width:150px; }
    col:nth-child(7) { width:360px; }
    @media (max-width:720px) {
      main { width:calc(100% - 20px); padding:14px 0 28px; }
      th, td { padding:11px 10px; font-size:13px; }
      table { min-width:1120px; }
      col:nth-child(1) { width:130px; }
      col:nth-child(2) { width:200px; }
      col:nth-child(3) { width:360px; }
    }
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <div class="table-wrap">
        <table>
          <colgroup><col/><col/><col/><col/><col/><col/><col/></colgroup>
          <thead>
            <tr>
              <th>요구사항 ID</th>
              <th>요구사항 명</th>
              <th>요구사항 설명</th>
              <th>유형</th>
              <th>우선순위</th>
              <th>출처</th>
              <th>맵핑</th>
            </tr>
          </thead>
          <tbody>${bodyRows}</tbody>
        </table>
      </div>
    </section>
  </main>
</body>
</html>`;
}

function selectUnwrittenTopic(topic) {
  rewriteRequestTopic = "";
  const draft = latestDraftForTopic(topic);
  if (draft) {
    selectDraft(draft);
    return;
  }
  selectedName = "";
  selectedDraft = null;
  selectedAnalysisReferenceId = "";
  selectedTaskDefinitionId = "";
  selectedRequirementTopic = "";
  exitEditMode(false);
  setTopicSelectValue(topic, { dispatch: true });
  updateRequestTopicSummary(getCurrentRequestTopic() || topic);
  showRequestWorkspace();
  clearPreview(false);
  renderList();
  renderPolicyTopicList();
  renderTopicChips(topicSearch?.value || "");
  updateCreateAvailability();
  focusWorkspaceOnCompact(requestArea);
}

function updateRequestTopicSummary(topic = "") {
  const selectedTopic = String(topic || "").trim();
  if (requestTopicName) {
    requestTopicName.textContent = selectedTopic || "-";
  }
  const summaryLabel = requestTopicSummary?.querySelector("span");
  if (summaryLabel) {
    summaryLabel.textContent = isRewriteRequestForTopic(selectedTopic) ? "다시 작성 대상" : "작성 대상";
  }
  if (requestTopicSummary) {
    requestTopicSummary.hidden = !selectedTopic;
  }
}

async function loadTopicScopes() {
  if (topicScopesLoaded) return topicScopeDefinitions;
  topicScopesLoaded = true;
  try {
    const response = await fetch(apiPath("/api/topic-scopes"));
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "작성 지침 정보를 불러오지 못했습니다.");
    }
    topicScopeDefinitions = data.definitions || {};
  } catch (_error) {
    topicScopeDefinitions = {};
  }
  renderRequestTopicDirection(topicSelect?.value || "");
  renderWorkspaceTopicDirectionForCurrent();
  return topicScopeDefinitions;
}

async function loadRequirementTopicCounts() {
  if (requirementTopicCountsLoaded || requirementTopicCountsLoading) return requirementTopicCounts;
  const topics = getTopicOptions();
  if (!topics.length) return requirementTopicCounts;
  requirementTopicCountsLoading = true;
  try {
    const params = new URLSearchParams();
    topics.forEach((topic) => params.append("topic", topic));
    const response = await fetch(apiPath(`/api/requirements-summary?${params.toString()}`));
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "요구사항 건수를 불러오지 못했습니다.");
    }
    requirementTopicCounts = {};
    (Array.isArray(data.topics) ? data.topics : []).forEach((item) => {
      const topic = String(item.topic || "").trim();
      if (!topic) return;
      requirementTopicCounts[normalizeTopic(topic)] = {
        requirementCount: Number(item.requirementCount || 0),
        detailRequirementCount: Number(item.detailRequirementCount || 0),
      };
    });
    requirementTopicCountsLoaded = true;
  } catch (_error) {
    requirementTopicCounts = await loadRequirementTopicCountsIndividually(topics);
    requirementTopicCountsLoaded = Object.keys(requirementTopicCounts).length > 0;
  } finally {
    requirementTopicCountsLoading = false;
    renderPolicyTopicList();
  }
  return requirementTopicCounts;
}

async function loadRequirementTopicCountsIndividually(topics = []) {
  const entries = await Promise.all(
    topics.map(async (topic) => {
      try {
        const response = await fetch(apiPath(`/api/requirements?topic=${encodeURIComponent(topic)}`));
        const data = await response.json();
        if (!response.ok || !data.ok) return null;
        return [
          normalizeTopic(topic),
          {
            requirementCount: Number(data.requirementCount || 0),
            detailRequirementCount: Number(data.detailRequirementCount || 0),
          },
        ];
      } catch (_error) {
        return null;
      }
    })
  );
  return Object.fromEntries(entries.filter(Boolean));
}

function topicScopeFor(topic = "") {
  const normalizedTopic = normalizeTopic(topic);
  if (!normalizedTopic) return null;
  return Object.values(topicScopeDefinitions || {}).find((item) => normalizeTopic(item.topic || "") === normalizedTopic) || null;
}

function isAgentDirectionLine(line = "") {
  return /개발\/QA|테스트 케이스|Agent|agent|Context|context|컨텍스트|내부 지침|검수 기준/.test(String(line || ""));
}

function topicDirectionLines(definition) {
  if (!definition) return [];
  const briefLines = String(definition.brief || "")
    .split(/\n+/)
    .map((line) => line.trim())
    .filter((line) => line && !/^\[.*\]$/.test(line))
    .map((line) => line.replace(/^-+\s*/, "").trim())
    .filter((line) => !isAgentDirectionLine(line))
    .filter(Boolean);
  if (briefLines.length > 0) {
    return briefLines.slice(0, 3);
  }
  const display = Array.isArray(definition.topicDirectionDisplay) ? definition.topicDirectionDisplay : [];
  const milestone = Array.isArray(definition.topicDirectionMilestone) ? definition.topicDirectionMilestone : [];
  const direction = Array.isArray(definition.direction) ? definition.direction : [];
  return [...display, ...milestone, ...direction]
    .map((item) => String(item || "").trim())
    .filter((line) => line && !isAgentDirectionLine(line))
    .slice(0, 3);
}

function renderRequestTopicDirection(topic = "") {
  if (!briefInput) return;
  const definition = topicScopeFor(topic);
  const autoBrief = String(definition?.brief || "").trim();
  const canReplace = !briefInput.value.trim() || (lastAutoBrief && briefInput.value === lastAutoBrief);
  if (!autoBrief) {
    if (canReplace) {
      briefInput.value = "";
      lastAutoBrief = "";
    }
    return;
  }
  if (canReplace) {
    briefInput.value = autoBrief;
    lastAutoBrief = autoBrief;
  }
}

function topicConceptColumns(definition) {
  const card = definition?.conceptCard;
  const columns = Array.isArray(card?.columns) ? card.columns : [];
  return columns
    .map((column) => ({
      label: String(column?.label || "").trim(),
      items: Array.isArray(column?.items) ? column.items.slice(0, 4) : [],
    }))
    .filter((column) => column.label && column.items.length > 0);
}

function hasTopicConceptCard(definition) {
  return Boolean(definition?.conceptCard && topicConceptColumns(definition).length > 0);
}

function stripDirectionPrefix(value = "") {
  return String(value || "")
    .replace(/^(지향점|PI 방향|고객 경험 혁신)\)\s*/u, "")
    .trim();
}

function conceptItemName(item = {}) {
  return String(item?.name || item?.id || "").trim();
}

function conceptItemId(item = {}) {
  return String(item?.id || "").trim();
}

function conceptItemDescription(item = {}) {
  return String(item?.description || "").trim();
}

function renderConceptMiniItems(items = [], limit = 3) {
  return items
    .slice(0, limit)
    .map((item) => {
      const id = conceptItemId(item);
      const name = conceptItemName(item);
      const description = conceptItemDescription(item);
      return `
        <li>
          ${id ? `<span>${escapeHtml(id)}</span>` : ""}
          <strong>${escapeHtml(name || "-")}</strong>
          ${description ? `<p>${escapeHtml(description)}</p>` : ""}
        </li>
      `;
    })
    .join("");
}

function topicConceptMessages(definition, card) {
  const directionLines = topicDirectionLines(definition).map(stripDirectionPrefix).filter(Boolean);
  const goal = stripDirectionPrefix(card?.goal || "");
  const messages = [goal, ...directionLines].filter(Boolean);
  const uniqueMessages = messages.filter((message, index) => messages.indexOf(message) === index);
  const fallback = [
    "고객 목적에서 출발해 업무 완료까지 끊기지 않는 흐름을 정의합니다.",
    "채널별로 달랐던 기준을 통합하고 운영 예외를 줄입니다.",
    "결과, 제한, 실패 복구 기준을 명확히 해 고객 신뢰를 높입니다.",
  ];
  const titles = ["고객 목적 중심", "PI 기준 표준화", "경험 완결성 강화"];
  return titles.map((title, index) => ({
    title,
    body: uniqueMessages[index] || fallback[index],
  }));
}

function topicConceptScopeRows(definition, columns) {
  const usecase = columns[0]?.items?.[0];
  const process = columns[1]?.items?.[0];
  const policy = columns[3]?.items?.[0] || columns[2]?.items?.[0];
  const focus = Array.isArray(definition?.focusPoints) ? definition.focusPoints[0] : "";
  return [
    ["업무 목적", stripDirectionPrefix(definition?.definition || "") || conceptItemName(usecase)],
    ["대표 과업", conceptItemName(usecase) || "고객 업무 완료 기준 수립"],
    ["핵심 흐름", conceptItemName(process) || "진입, 판단, 실행, 결과 확인 흐름"],
    ["정책 판단", conceptItemName(policy) || focus || "허용, 제한, 예외, 이력 기준"],
  ].filter((row) => row[1]);
}

function topicConceptDirectionCards(definition, card) {
  const lines = topicDirectionLines(definition).map(stripDirectionPrefix).filter(Boolean);
  const goal = stripDirectionPrefix(card?.goal || "");
  const fallback = [
    stripDirectionPrefix(definition?.definition || "") || "고객 과업을 기준으로 업무 범위와 완료 기준을 명확히 정의합니다.",
    "채널별로 흩어진 기준을 통합하고 중복·수작업·예외 운영을 줄입니다.",
    "고객이 결과와 제한, 실패 후 다음 행동을 예측할 수 있도록 정책 기준을 구체화합니다.",
  ];
  const values = [goal, ...lines, ...fallback].filter(Boolean);
  const unique = values.filter((value, index) => values.indexOf(value) === index).slice(0, 3);
  const titles = ["전략 방향", "PI 방향", "고객 경험 혁신"];
  return titles.map((title, index) => ({
    title,
    body: unique[index] || fallback[index],
  }));
}

function topicConceptPrinciples(definition, card) {
  const directions = topicConceptDirectionCards(definition, card);
  const focus = Array.isArray(definition?.focusPoints) ? definition.focusPoints : [];
  const questions = Array.isArray(definition?.policyQuestions) ? definition.policyQuestions : [];
  return [
    {
      title: "고객 목적 중심",
      body: directions[0]?.body || "고객이 끝내려는 업무 목적 기준으로 범위와 완료 상태를 정의합니다.",
    },
    {
      title: "PI 기준 통합",
      body: directions[1]?.body || "분산된 업무 진입, 판단, 실행 기준을 하나의 흐름으로 통합합니다.",
    },
    {
      title: "정책 판단 구체화",
      body: questions[0] || focus[0] || "허용, 제한, 예외, 고지, 이력 기준을 사람이 해석하지 않아도 되도록 구체화합니다.",
    },
    {
      title: "실행 전 고객 확인",
      body: "요금, 혜택, 권한, 상태 변경처럼 고객 영향이 있는 업무는 실행 전 조건과 결과를 명확히 확인합니다.",
    },
    {
      title: "복구 가능한 실패",
      body: "무결과, 제한, 오류, 보류 상태에서도 고객의 다음 행동과 상담·재시도·대체 경로를 남깁니다.",
    },
  ];
}

function topicConceptJourneySteps(columns) {
  const labels = ["고객 과업", "업무 흐름", "처리 역량", "정책 기준"];
  return labels.map((label, index) => {
    const column = columns[index];
    const item = column?.items?.[0];
    return {
      label: column?.label || label,
      title: conceptItemName(item) || `${label} 정리`,
      description: conceptItemDescription(item) || `${label}의 대표 기준을 확인하고 다음 단계와 연결합니다.`,
    };
  });
}

function renderTopicConceptSummaryItems(items = [], limit = 4) {
  return items
    .slice(0, limit)
    .map((item) => {
      const id = conceptItemId(item);
      const name = conceptItemName(item);
      return `
        <li>
          ${id ? `<small>${escapeHtml(id)}</small>` : ""}
          ${escapeHtml(name || "-")}
        </li>
      `;
    })
    .join("");
}

function renderTopicConceptPanel(definition) {
  const card = definition?.conceptCard;
  const visibleColumns = topicConceptColumns(definition);
  if (!card || visibleColumns.length === 0) return "";
  const goal = String(card.goal || "").trim();
  const topic = String(definition?.topic || "").trim() || "선택 주제";
  const directions = topicConceptDirectionCards(definition, card);
  const principles = topicConceptPrinciples(definition, card);
  const journeySteps = topicConceptJourneySteps(visibleColumns);
  const scopeRows = topicConceptScopeRows(definition, visibleColumns);
  const processItems = visibleColumns.find((column) => column.label.includes("흐름"))?.items || visibleColumns[1]?.items || [];
  const functionItems = visibleColumns.find((column) => column.label.includes("역량"))?.items || visibleColumns[2]?.items || [];
  const policyItems = visibleColumns.find((column) => column.label.includes("정책"))?.items || visibleColumns[3]?.items || [];
  return `
    <article class="topic-strategy-poster">
      <header class="topic-strategy-poster-hero">
        <p class="topic-strategy-poster-eyebrow">Policy Strategy Map</p>
        <h3>${escapeHtml(topic)} 정책서는 고객 과업에서 실행·검증까지 이어지는 통합 설계도다</h3>
        ${goal ? `<p>${escapeHtml(stripDirectionPrefix(goal))}</p>` : ""}
        <dl class="topic-strategy-poster-meta">
          <div><dt>요약 기준</dt><dd>작성 지침</dd></div>
          <div><dt>구성</dt><dd>과업→흐름→기능→정책</dd></div>
          <div><dt>검토 관점</dt><dd>CX · PI · QA</dd></div>
        </dl>
      </header>

      <section class="topic-strategy-poster-section">
        <h4><span>01</span>작성 지침</h4>
        <div class="topic-strategy-direction-grid">
          ${directions
            .map((direction, index) => `
              <article class="topic-strategy-direction-card">
                <span>${index + 1}</span>
                <div>
                  <strong>${escapeHtml(direction.title)}</strong>
                  <p>${escapeHtml(direction.body)}</p>
                </div>
              </article>
            `)
            .join("")}
        </div>
      </section>

      <section class="topic-strategy-poster-section">
        <h4><span>02</span>설계 원칙</h4>
        <div class="topic-strategy-principles-vertical">
          ${principles
            .map((principle, index) => `
              <article class="topic-strategy-principle-vertical">
                <div><span>${index + 1}</span><strong>${escapeHtml(principle.title)}</strong></div>
                <p>${escapeHtml(principle.body)}</p>
              </article>
            `)
            .join("")}
        </div>
      </section>

      <section class="topic-strategy-poster-section topic-strategy-journey-vertical">
        <h4><span>03</span>설계 구조</h4>
        <div class="topic-strategy-journey-flow">
          ${journeySteps
            .map((step, index) => `
              <article class="topic-strategy-journey-node">
                <span>${index + 1}</span>
                <div>
                  <b>${escapeHtml(step.label)}</b>
                  <strong>${escapeHtml(step.title)}</strong>
                  <p>${escapeHtml(step.description)}</p>
                </div>
              </article>
            `)
            .join("")}
        </div>
      </section>

      <section class="topic-strategy-poster-section">
        <h4><span>04</span>주요 프로세스와 기능·정책</h4>
        <div class="topic-strategy-summary-grid">
          <article>
            <h5>핵심 프로세스</h5>
            <ul>${renderTopicConceptSummaryItems(processItems, 4)}</ul>
          </article>
          <article>
            <h5>기능 요약</h5>
            <ul>${renderTopicConceptSummaryItems(functionItems, 4)}</ul>
          </article>
          <article>
            <h5>정책 기준</h5>
            <ul>${renderTopicConceptSummaryItems(policyItems, 4)}</ul>
          </article>
        </div>
      </section>

      <section class="topic-strategy-poster-section">
        <h4><span>05</span>적용 범위</h4>
        <table class="topic-strategy-scope-table">
          <tbody>
            ${scopeRows
              .map((row) => `
                <tr>
                  <th>${escapeHtml(row[0])}</th>
                  <td>${escapeHtml(row[1])}</td>
                </tr>
              `)
              .join("")}
          </tbody>
        </table>
      </section>

      <footer class="topic-strategy-conclusion">
        <b>결론</b>
        <p>${escapeHtml(topic)} 정책서는 고객 과업을 기준으로 흐름, 기능, 정책 판단값을 연결해 실행 가능하고 검증 가능한 통합채널 기준으로 관리합니다.</p>
      </footer>
    </article>
  `;
}

function openTopicConceptModal(topic = "") {
  if (!topicConceptModal || !topicConceptBody) return;
  const definition = topicScopeFor(topic);
  if (!hasTopicConceptCard(definition)) {
    setMessage("표시할 주제 체계도 정보가 아직 없습니다.", true);
    return;
  }
  const displayTopic = definition?.topic || topic || "선택 주제";
  if (topicConceptTitle) {
    topicConceptTitle.textContent = `${displayTopic} 전략 체계도`;
  }
  if (topicConceptSummary) {
    topicConceptSummary.textContent = "작성 지침과 설계 원칙을 먼저 확인하고, 주요 프로세스·기능·정책을 이어서 봅니다.";
  }
  topicConceptBody.innerHTML = renderTopicConceptPanel(definition);
  topicConceptModal.hidden = false;
  trackUserEvent("topic_concept_modal_opened", { topic: displayTopic });
}

function closeTopicConceptModal() {
  if (!topicConceptModal) return;
  topicConceptModal.hidden = true;
}

function openWidePreviewModal() {
  if (!widePreviewModal || !widePreviewFrame) return;
  if (isEditing) {
    setMessage("직접 편집 중에는 와이드뷰를 사용할 수 없습니다. 편집을 완료하거나 취소해 주세요.", true);
    return;
  }
  const hasPreviewTarget = Boolean(selectedName || hasAnalysisReferenceSelection());
  if (!hasPreviewTarget || !previewFrame?.contentDocument) {
    setMessage("와이드뷰로 볼 문서를 먼저 선택해 주세요.", true);
    return;
  }
  widePreviewRestoreFocusTarget = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  syncWidePreviewFromCurrentFrame();
  widePreviewModal.hidden = false;
  widePreviewCloseButton?.focus();
  trackUserEvent("wide_preview_opened", {
    selectedName,
    analysisReference: selectedAnalysisReferenceId || "",
  });
}

function closeWidePreviewModal() {
  if (!widePreviewModal) return;
  widePreviewModal.hidden = true;
  if (widePreviewFrame) {
    widePreviewFrame.removeAttribute("src");
    widePreviewFrame.srcdoc = "";
  }
  if (widePreviewRestoreFocusTarget && typeof widePreviewRestoreFocusTarget.focus === "function") {
    widePreviewRestoreFocusTarget.focus();
  }
  widePreviewRestoreFocusTarget = null;
}

function renderWorkspaceTopicDirection(topic = "") {
  if (!workspaceTopicDirection) return;
  const definition = topicScopeFor(topic);
  const lines = topicDirectionLines(definition);
  if (!topic || lines.length === 0) {
    workspaceTopicDirection.hidden = true;
    workspaceTopicDirection.innerHTML = "";
    workspaceDirectionEditMode = false;
    workspaceDirectionTopic = "";
    return;
  }
  const editing = canCurrentUserWritePolicies() && workspaceDirectionEditMode && normalizeTopic(workspaceDirectionTopic) === normalizeTopic(topic);
  const lineText = lines.join("\n");
  workspaceTopicDirection.hidden = false;
  workspaceDirectionTopic = topic;
  workspaceTopicDirection.innerHTML = editing
    ? `
    <div class="workspace-topic-direction-head">
      <div>
        <p class="eyebrow">Writing Direction</p>
        <strong>작성 지침</strong>
      </div>
      <div class="workspace-topic-direction-actions">
        <button class="ghost-button compact" type="button" data-topic-direction-save ${workspaceDirectionSaving ? "disabled" : ""}>
          ${workspaceDirectionSaving ? "저장 중" : "수정 완료"}
        </button>
      </div>
    </div>
    <div class="workspace-topic-direction-editor">
      <textarea data-topic-direction-editor rows="4" aria-label="작성 지침 수정">${escapeHtml(lineText)}</textarea>
    </div>
  `
    : `
    <div class="workspace-topic-direction-head">
      <div>
        <p class="eyebrow">Writing Direction</p>
        <strong>작성 지침</strong>
      </div>
      <div class="workspace-topic-direction-actions">
        ${canCurrentUserWritePolicies() ? '<button class="ghost-button compact" type="button" data-topic-direction-edit>수정</button>' : ""}
        ${hasTopicConceptCard(definition) ? '<button class="ghost-button compact workspace-topic-concept-button" type="button" data-topic-concept-open>체계도</button>' : ""}
      </div>
    </div>
    <ul class="workspace-topic-direction-list">
      ${lines.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
    </ul>
  `;
  bindWorkspaceTopicDirectionActions(topic);
}

function bindWorkspaceTopicDirectionActions(topic = "") {
  const editButton = workspaceTopicDirection?.querySelector("[data-topic-direction-edit]");
  const saveButton = workspaceTopicDirection?.querySelector("[data-topic-direction-save]");
  editButton?.addEventListener("click", () => {
    if (!guardWritePermission("조회 권한은 작성 지침 수정을 실행할 수 없습니다.")) return;
    workspaceDirectionEditMode = true;
    workspaceDirectionTopic = topic;
    renderWorkspaceTopicDirection(topic);
    workspaceTopicDirection?.querySelector("[data-topic-direction-editor]")?.focus();
  });
  saveButton?.addEventListener("click", () => saveWorkspaceTopicDirection(topic));
  workspaceTopicDirection?.querySelector("[data-topic-concept-open]")?.addEventListener("click", () => {
    openTopicConceptModal(topic);
  });
}

async function saveWorkspaceTopicDirection(topic = "") {
  if (!workspaceTopicDirection || workspaceDirectionSaving) return;
  if (!guardWritePermission("조회 권한은 작성 지침 수정을 실행할 수 없습니다.")) return;
  const editor = workspaceTopicDirection.querySelector("[data-topic-direction-editor]");
  const lines = String(editor?.value || "")
    .split(/\n+/)
    .map((line) => line.trim().replace(/^-+\s*/, ""))
    .filter(Boolean)
    .slice(0, 3);
  if (lines.length === 0) {
    setMessage("작성 지침을 1개 이상 입력해 주세요.", true);
    editor?.focus();
    return;
  }
  const saveButton = workspaceTopicDirection.querySelector("[data-topic-direction-save]");
  workspaceDirectionSaving = true;
  if (saveButton) {
    saveButton.disabled = true;
    saveButton.textContent = "저장 중";
  }
  try {
    const response = await fetch(apiPath("/api/topic-scopes/update"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({ topic, lines })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "작성 지침을 저장하지 못했습니다.");
    }
    if (data.definition?.topic) {
      topicScopeDefinitions[data.definition.topic] = data.definition;
    }
    workspaceDirectionEditMode = false;
    workspaceDirectionSaving = false;
    const activeTopic = selectedDraft?.topic || selectedPolicyItem()?.topic || topic;
    renderWorkspaceTopicDirection(activeTopic);
    renderRequestTopicDirection(topicSelect?.value || "");
    setMessage(data.knowledgeRefresh === "queued" ? "작성 지침을 업데이트했습니다. 지식 갱신은 백그라운드에서 이어집니다." : "작성 지침을 업데이트했습니다.");
  } catch (error) {
    workspaceDirectionSaving = false;
    if (saveButton) {
      saveButton.disabled = false;
      saveButton.textContent = "수정 완료";
    }
    setMessage(error.message || "작성 지침 저장 중 오류가 발생했습니다.", true);
    editor?.focus();
  }
}

function renderWorkspaceTopicDirectionForCurrent() {
  if (selectedDraft?.topic) {
    renderWorkspaceTopicDirection(selectedDraft.topic);
    return;
  }
  const item = currentItems.find((candidate) => candidate.name === selectedName);
  renderWorkspaceTopicDirection(item?.topic || "");
}

function latestItemForTopic(topic) {
  const matches = currentItems.filter((item) => normalizeTopic(item.topic) === normalizeTopic(topic));
  if (matches.length === 0) return null;
  return matches.slice().sort((a, b) => comparePolicyVersion(b.version, a.version))[0];
}

function latestDraftForTopic(topic) {
  const matches = currentDrafts.filter((draft) => normalizeTopic(draft.topic) === normalizeTopic(topic));
  if (matches.length === 0) return null;
  return matches.slice().sort((a, b) => String(b.savedAt || b.modified || "").localeCompare(String(a.savedAt || a.modified || "")))[0];
}

function isPolicyCompleted(item) {
  return item?.lifecycle?.status === "completed";
}

function selectedPolicyItem() {
  if (!selectedName) return null;
  return currentItems.find((candidate) => candidate.name === selectedName) || null;
}

function selectedPolicyCompleted() {
  return isPolicyCompleted(selectedPolicyItem());
}

function canCreateFullVersionFromSelectedPolicy() {
  const item = selectedPolicyItem();
  return Boolean(item && item.templateType === "simple" && isPolicyCompleted(item));
}

function policyTopicStatus(item, draft = null) {
  if (!item) {
    if (draft) {
      return { text: "작성 중단", label: "중간 결과가 보관되어 이어서 작성할 수 있습니다.", className: "draft" };
    }
    return { text: "미작성", label: "미작성", className: "empty" };
  }
  if (isPolicyCompleted(item)) {
    return { text: "작성 완료", label: "사람이 최종 작성 완료로 확정했습니다.", className: "done" };
  }
  if (item.specSync?.needed) {
    return { text: "작성 중", label: "직접 수정된 HTML 기준으로 spec 보정이 필요합니다.", className: "inprogress" };
  }
  const qualityStatus = item.quality?.status;
  const inspectionStatus = item.inspection?.status;
  if (qualityStatus === "fail" || inspectionStatus === "fail") {
    return { text: "작성 중", label: "최종 검수에서 보완이 필요해 사람이 확인 중인 상태입니다.", className: "inprogress" };
  }
  if (qualityStatus === "pass" || inspectionStatus === "pass" || inspectionStatus === "warn") {
    return { text: "작성 중", label: "1차 작성 후 사람이 보완 중인 상태입니다.", className: "inprogress" };
  }
  return { text: "작성 중", label: "정책서 파일이 생성되어 있으며 사람 검토를 기다립니다.", className: "inprogress" };
}

function comparePolicyVersion(left, right) {
  const a = parseVersion(left);
  const b = parseVersion(right);
  if (a.major !== b.major) return a.major - b.major;
  return a.minor - b.minor;
}

function parseVersion(version) {
  const match = String(version || "").match(/v(\d+)\.(\d+)/);
  return {
    major: match ? Number(match[1]) : 0,
    minor: match ? Number(match[2]) : 0,
  };
}

async function loadHealth() {
  if (!llmStatus) return;
  try {
    const response = await fetch(apiPath("/api/health"));
    const data = await response.json();
    if (!data.ok || !data.llm?.enabled) {
      llmStatus.textContent = data.llm?.error || "LLM 설정 필요";
      llmStatus.className = "llm-status error";
      return;
    }
    const routingLabel = data.llm.routing ? "역할별 라우팅 적용" : (data.llm.reasoningEffort || "reasoning 기본값");
    llmStatus.textContent = `${data.llm.model} · ${routingLabel}`;
    llmStatus.className = "llm-status";
  } catch (error) {
    llmStatus.textContent = "LLM 설정 확인 실패";
    llmStatus.className = "llm-status error";
  }
}

async function loadDashboard() {
  try {
    const response = await fetch(apiPath("/api/dashboard"));
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok || !data.ok) {
      throw new Error(data?.error || "대시보드 데이터를 불러오지 못했습니다.");
    }
    currentDashboard = data;
    renderAgentDashboard(data.agents);
  } catch (error) {
    currentDashboard = null;
    renderAgentDashboard(null, error.message);
  }
}

async function openServiceHealthModal() {
  if (serviceHealthModal) serviceHealthModal.hidden = false;
  await loadServiceHealth();
}

function closeServiceHealthModal() {
  if (serviceHealthModal) serviceHealthModal.hidden = true;
}

async function openUserManagementModal() {
  if (!canCurrentUserManageUsers()) {
    setMessage("사용자 관리는 관리자만 확인할 수 있습니다.", true);
    return;
  }
  if (userManagementModal) userManagementModal.hidden = false;
  await loadUserManagement();
}

function closeUserManagementModal() {
  if (userManagementModal) userManagementModal.hidden = true;
}

async function loadUserManagement() {
  if (userManagementInFlight) return;
  userManagementInFlight = true;
  setUserManagementLoading(true);
  try {
    const response = await fetch(apiPath("/api/admin/users"));
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok || !data?.ok) {
      throw new Error(data?.error || "사용자 목록을 불러오지 못했습니다.");
    }
    renderUserManagement(data.users);
  } catch (error) {
    renderUserManagementError(error.message);
  } finally {
    userManagementInFlight = false;
    setUserManagementLoading(false);
  }
}

async function withdrawManagedUser(employeeId, name, button) {
  const normalizedEmployeeId = String(employeeId || "").trim();
  if (!normalizedEmployeeId) return;
  if (!canCurrentUserManageUsers()) {
    setMessage("사용자 관리는 관리자만 처리할 수 있습니다.", true);
    return;
  }
  const confirmed = window.confirm(`${name || normalizedEmployeeId} 사용자를 탈퇴 처리할까요?\n탈퇴 처리 후 해당 계정은 로그인할 수 없습니다.`);
  if (!confirmed) return;
  const originalText = button?.textContent || "탈퇴 처리";
  if (button) {
    button.disabled = true;
    button.textContent = "처리 중";
  }
  try {
    const response = await fetch(apiPath("/api/admin/users/withdraw"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({ employeeId: normalizedEmployeeId })),
    });
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok || !data?.ok) {
      throw new Error(data?.error || "탈퇴 처리에 실패했습니다.");
    }
    renderUserManagement(data.users);
    setMessage(`${name || normalizedEmployeeId} 사용자를 탈퇴 처리했습니다.`);
  } catch (error) {
    setMessage(error.message || "탈퇴 처리에 실패했습니다.", true);
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

async function updateManagedUserRole(employeeId, role, select) {
  const normalizedEmployeeId = String(employeeId || "").trim();
  const nextRole = currentUserRoleFromValue(role);
  const originalRole = currentUserRoleFromValue(select?.getAttribute("data-original-role") || "user");
  if (!normalizedEmployeeId) return;
  if (!canCurrentUserManageUsers()) {
    setMessage("사용자 관리는 관리자만 처리할 수 있습니다.", true);
    if (select) select.value = originalRole;
    return;
  }
  if (nextRole === originalRole) return;
  if (select) select.disabled = true;
  try {
    const response = await fetch(apiPath("/api/admin/users/role"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({ employeeId: normalizedEmployeeId, role: nextRole })),
    });
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok || !data?.ok) {
      throw new Error(data?.error || "권한 변경에 실패했습니다.");
    }
    renderUserManagement(data.users);
    setMessage(`${data.user?.name || normalizedEmployeeId} 사용자의 권한을 '${currentUserRoleLabel(data.user?.role)}'로 변경했습니다.`);
  } catch (error) {
    setMessage(error.message || "권한 변경에 실패했습니다.", true);
    if (select) {
      select.value = originalRole;
      select.disabled = false;
    }
  }
}

function setUserManagementLoading(isLoading) {
  if (userManagementRefreshButton) userManagementRefreshButton.disabled = isLoading;
  if (userManagementRefreshButton) userManagementRefreshButton.textContent = isLoading ? "확인 중" : "목록 새로고침";
}

function renderUserManagement(usersPayload) {
  const summary = usersPayload?.summary || {};
  const items = Array.isArray(usersPayload?.items) ? usersPayload.items : [];
  const approvalRequired = Boolean(usersPayload?.approvalRequired);
  if (userManagementSummary) {
    userManagementSummary.textContent = `${formatDate(usersPayload?.generatedAt)} 기준 가입 사용자 ${summary.totalUsers || 0}명을 확인했습니다. ${approvalRequired ? "현재 신규 가입은 승인 후 이용 구조입니다." : "현재 신규 가입 사용자는 즉시 이용 가능합니다."}`;
  }
  if (userManagementCount) userManagementCount.textContent = `${items.length}명`;
  if (userManagementStats) {
    const stats = [
      ["전체 사용자", summary.totalUsers || 0],
      ["이용 가능", summary.approvedUsers || 0],
      ["편집자", summary.normalUsers || 0],
      ["조회자", summary.viewerUsers || 0],
      ["승인 대기", summary.pendingUsers || 0],
      ["비활성", summary.inactiveUsers || 0],
    ];
    userManagementStats.innerHTML = stats
      .map(([label, value]) => `
        <div class="service-health-stat ${label === "승인 대기" && Number(value) > 0 ? "risk" : ""}">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `)
      .join("");
  }
  if (!userManagementList) return;
  if (!items.length) {
    userManagementList.classList.add("empty");
    userManagementList.textContent = "아직 가입된 사용자가 없습니다.";
    return;
  }
  userManagementList.classList.remove("empty");
  userManagementList.innerHTML = `
    <div class="user-management-table-wrap">
      <table class="user-management-table">
        <thead>
          <tr>
            <th>이름</th>
            <th>사번</th>
            <th>상태</th>
            <th>권한</th>
            <th>가입일</th>
            <th>최근 로그인일</th>
            <th>관리</th>
          </tr>
        </thead>
        <tbody>
          ${items.map(renderUserManagementRow).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderUserManagementRow(user) {
  const active = user?.active !== false;
  const approved = user?.approved !== false;
  const status = !active ? "비활성" : approved ? "이용 가능" : "승인 대기";
  const tone = !active ? "muted" : approved ? "done" : "waiting";
  const role = currentUserRoleFromValue(user?.role);
  const lastLoginAt = user?.lastLoginAt ? formatDate(user.lastLoginAt) : "최근 로그인 없음";
  const employeeId = String(user?.employeeId || "");
  const isSelf = employeeId.trim().toLowerCase() === String(currentUser?.employeeId || "").trim().toLowerCase();
  const isManager = USER_MANAGEMENT_EMPLOYEE_IDS.has(employeeId.trim().toLowerCase());
  const disabled = !active || isSelf || isManager;
  const roleDisabled = disabled || !approved;
  const actionLabel = !active ? "탈퇴 완료" : isSelf ? "본인" : isManager ? "관리자" : "탈퇴 처리";
  return `
    <tr>
      <td><strong>${escapeHtml(user?.name || "-")}</strong></td>
      <td><span class="mono">${escapeHtml(user?.employeeId || "-")}</span></td>
      <td><span class="user-status-pill ${tone}">${escapeHtml(status)}</span></td>
      <td>
        <select
          class="user-role-select"
          data-user-role-select="1"
          data-employee-id="${escapeHtml(employeeId)}"
          data-original-role="${escapeHtml(role)}"
          aria-label="${escapeHtml(user?.name || employeeId)} 권한"
          ${roleDisabled ? "disabled" : ""}
        >
          <option value="user" ${role === "user" ? "selected" : ""}>편집자</option>
          <option value="viewer" ${role === "viewer" ? "selected" : ""}>조회자</option>
        </select>
      </td>
      <td>${escapeHtml(formatDate(user?.createdAt))}</td>
      <td>${escapeHtml(lastLoginAt)}</td>
      <td>
        <button
          class="ghost-button compact user-withdraw-button ${disabled ? "" : "danger"}"
          type="button"
          data-user-withdraw="1"
          data-employee-id="${escapeHtml(employeeId)}"
          data-user-name="${escapeHtml(user?.name || employeeId)}"
          ${disabled ? "disabled" : ""}
        >${escapeHtml(actionLabel)}</button>
      </td>
    </tr>
  `;
}

function currentUserRoleFromValue(value) {
  const raw = String(value || "user").trim().toLowerCase();
  if (["viewer", "view", "read", "readonly", "read_only", "조회", "조회자"].includes(raw)) return "viewer";
  return "user";
}

function renderUserManagementError(messageText) {
  if (userManagementSummary) userManagementSummary.textContent = messageText || "사용자 목록을 확인할 수 없습니다.";
  if (userManagementStats) userManagementStats.innerHTML = "";
  if (userManagementCount) userManagementCount.textContent = "0명";
  if (userManagementList) {
    userManagementList.classList.add("empty");
    userManagementList.innerHTML = `<div class="service-health-item risk"><strong>확인 실패</strong><p>${escapeHtml(messageText || "")}</p></div>`;
  }
}

async function loadServiceHealth() {
  if (serviceHealthInFlight) return;
  serviceHealthInFlight = true;
  setServiceHealthLoading(true);
  try {
    const response = await fetch(apiPath("/api/admin/service-health"));
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok || !data?.ok) {
      throw new Error(data?.error || "서비스 상태를 불러오지 못했습니다.");
    }
    renderServiceHealth(data.service);
  } catch (error) {
    renderServiceHealthError(error.message);
  } finally {
    serviceHealthInFlight = false;
    setServiceHealthLoading(false);
  }
}

async function cleanupServiceLocks() {
  if (serviceHealthInFlight || !serviceLockCleanupButton) return;
  if (!guardWritePermission("조회 권한은 서비스 기록 정리를 실행할 수 없습니다.")) return;
  serviceHealthInFlight = true;
  serviceLockCleanupButton.disabled = true;
  serviceLockCleanupButton.textContent = "정리 중";
  try {
    const response = await fetch(apiPath("/api/admin/locks/cleanup"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(withClientSession({})),
    });
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok || !data?.ok) {
      throw new Error(data?.error || "작업 점유 기록 정리에 실패했습니다.");
    }
    renderServiceHealth(data.service);
    const deletedCount = Array.isArray(data.deleted) ? data.deleted.length : 0;
    if (serviceHealthSummary) {
      serviceHealthSummary.textContent = deletedCount
        ? `정리 가능한 작업 점유 기록 ${deletedCount}건을 정리했습니다.`
        : "정리할 오래된/종료 기록이 없습니다. 현재 진행 중인 작업은 그대로 유지됩니다.";
    }
  } catch (error) {
    renderServiceHealthError(error.message);
  } finally {
    serviceHealthInFlight = false;
    if (serviceLockCleanupButton) serviceLockCleanupButton.textContent = "오래된/종료 기록 정리";
  }
}

function setServiceHealthLoading(isLoading) {
  if (serviceHealthRefreshButton) serviceHealthRefreshButton.disabled = isLoading;
  if (serviceHealthRefreshButton) serviceHealthRefreshButton.textContent = isLoading ? "확인 중" : "상태 새로고침";
  if (isLoading && serviceLockCleanupButton) serviceLockCleanupButton.disabled = true;
}

function renderServiceHealth(service) {
  const summary = service?.summary || {};
  const status = service?.status || "healthy";
  if (serviceHealthSummary) {
    const label = status === "risk" ? "주의가 필요한 상태" : status === "warning" ? "확인할 항목 있음" : "정상 범위";
    serviceHealthSummary.textContent = `${label} · ${formatDate(service?.generatedAt)} 기준으로 작업 점유 기록, 작업, LLM, 디스크를 확인했습니다.`;
  }
  if (serviceHealthStats) {
    const disk = service?.disk || {};
    const stats = [
      ["진행 중 기록", summary.activeLocks || 0],
      ["만료 기록", summary.staleLocks || 0],
      ["진행 작업", summary.activeJobs || 0],
      ["대기 작업", summary.queuedJobs || 0],
      ["사용 가능 슬롯", summary.availableQueueSlots ?? "-"],
      ["LLM 오류", summary.recentLlmErrors || 0],
      ["재시도", summary.recentLlmRetries || 0],
      ["사용 이벤트", summary.recentUserEvents || 0],
      ["사용 오류", summary.recentUiErrors || 0],
      ["디스크", formatSize(summary.diskUsageBytes || 0)],
    ];
    if (Number(disk.untrackedPersistentBytes || 0) > 0) {
      stats.push(["미집계", formatSize(disk.untrackedPersistentBytes || 0)]);
    }
    serviceHealthStats.innerHTML = stats
      .map(([label, value]) => {
        const isRiskStat = (label === "만료 기록" && Number(value) > 0)
          || (label === "미집계" && Number(disk.untrackedPersistentBytes || 0) > 0);
        return `
        <div class="service-health-stat ${isRiskStat ? "risk" : ""}">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `;
      })
      .join("");
  }
  renderServiceRecommendations(service?.recommendations || []);
  renderServiceDisk(service?.disk || {});
  renderServiceLocks(service?.locks?.items || [], service?.locks?.summary || {});
  renderServiceQueue(service?.queue || {});
  renderServiceRuntime(service?.jobs?.items || [], service?.llm || {});
  renderServiceUsage(service?.usage || {});
}

function renderServiceHealthError(messageText) {
  if (serviceHealthSummary) serviceHealthSummary.textContent = messageText || "서비스 상태를 확인할 수 없습니다.";
  if (serviceHealthStats) serviceHealthStats.innerHTML = "";
  if (serviceRecommendationList) serviceRecommendationList.innerHTML = `<div class="service-health-item risk"><strong>확인 실패</strong><p>${escapeHtml(messageText || "")}</p></div>`;
  if (serviceDiskList) serviceDiskList.innerHTML = '<div class="service-health-empty">디스크 상세를 확인할 수 없습니다.</div>';
  if (serviceLockList) serviceLockList.innerHTML = '<div class="service-health-empty">작업 점유 기록을 확인할 수 없습니다.</div>';
  if (serviceQueueList) serviceQueueList.innerHTML = '<div class="service-health-empty">큐 정보를 확인할 수 없습니다.</div>';
  if (serviceRuntimeList) serviceRuntimeList.innerHTML = '<div class="service-health-empty">실행 정보를 확인할 수 없습니다.</div>';
  if (serviceUsageList) serviceUsageList.innerHTML = '<div class="service-health-empty">사용 로그를 확인할 수 없습니다.</div>';
  if (serviceLockCleanupButton) serviceLockCleanupButton.disabled = true;
}

function renderServiceRecommendations(items) {
  if (serviceRecommendationCount) serviceRecommendationCount.textContent = `${items.length}건`;
  if (!serviceRecommendationList) return;
  if (!items.length) {
    serviceRecommendationList.classList.add("empty");
    serviceRecommendationList.textContent = "운영 권고가 없습니다.";
    return;
  }
  serviceRecommendationList.classList.remove("empty");
  serviceRecommendationList.innerHTML = items
    .map((item) => `
      <div class="service-health-item ${escapeHtml(item.severity || "info")}">
        <strong>${escapeHtml(item.title || "운영 권고")}</strong>
        <p>${escapeHtml(item.body || "")}</p>
      </div>
    `)
    .join("");
}

function renderServiceDisk(disk) {
  const children = Array.isArray(disk?.persistentRootChildren) ? disk.persistentRootChildren : [];
  if (serviceDiskCount) serviceDiskCount.textContent = `${children.length}개`;
  if (!serviceDiskList) return;
  const rootLabel = disk?.persistentRoot || "persistent root 미확인";
  const summaryRows = [
    ["persistent root", rootLabel],
    ["persistent 전체", formatSize(disk?.persistentRootBytes || 0)],
    ["output", formatSize(disk?.outputBytes || 0)],
    ["reports", formatSize(disk?.reportsBytes || 0)],
    ["미집계", formatSize(disk?.untrackedPersistentBytes || 0)],
    ["삭제 후 점유", disk?.deletedOpenFileCheckSupported === false ? "확인 불가" : formatSize(disk?.deletedOpenFileBytes || 0)],
  ];
  const childRows = children.slice(0, 8).map((item) => `
    <div class="service-disk-row">
      <span>${escapeHtml(item.name || "-")}</span>
      <strong>${escapeHtml(formatSize(item.sizeBytes || 0))}</strong>
    </div>
  `).join("");
  const deletedOpenFiles = Array.isArray(disk?.deletedOpenFiles) ? disk.deletedOpenFiles : [];
  const deletedOpenRows = deletedOpenFiles.slice(0, 5).map((item) => `
    <div class="service-disk-row warning">
      <span>${escapeHtml([item.process, item.path].filter(Boolean).join(" · ") || "-")}</span>
      <strong>${escapeHtml(formatSize(item.sizeBytes || 0))}</strong>
    </div>
  `).join("");
  serviceDiskList.classList.remove("empty");
  serviceDiskList.innerHTML = `
    <div class="service-disk-summary">
      ${summaryRows.map(([label, value]) => `
        <div>
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `).join("")}
    </div>
    ${childRows ? `<div class="service-disk-children">${childRows}</div>` : '<div class="service-health-empty">persistent root 하위 항목이 없습니다.</div>'}
    ${deletedOpenRows ? `<div class="service-queue-subtitle">삭제됐지만 열려 있는 파일</div><div class="service-disk-children">${deletedOpenRows}</div>` : ""}
  `;
}

function renderServiceLocks(items, summary) {
  const blockingItems = (Array.isArray(items) ? items : []).filter((item) => item?.active);
  if (serviceLockCount) serviceLockCount.textContent = `${blockingItems.length}건`;
  if (serviceLockCleanupButton) {
    serviceLockCleanupButton.disabled = Number(summary.cleanupCandidates || 0) === 0 || !canCurrentUserWritePolicies();
  }
  if (!serviceLockList) return;
  if (!blockingItems.length) {
    serviceLockList.classList.add("empty");
    serviceLockList.textContent = Number(summary.cleanupCandidates || 0) > 0
      ? "현재 다른 사용자의 작업을 막는 점유 기록은 없습니다. 오래된/종료 기록은 상단 정리 버튼으로 정리할 수 있습니다."
      : "현재 다른 사용자의 작업을 막는 점유 기록이 없습니다.";
    return;
  }
  serviceLockList.classList.remove("empty");
  serviceLockList.innerHTML = blockingItems
    .map((item) => {
      const title = item.file || item.topic || item.lockKey || item.fileName;
      const remain = `남은 보호 시간 ${formatSeconds(item.remainingSeconds)}`;
      return `
        <div class="service-lock-row warning">
          <div>
            <strong>${escapeHtml(title || "-")}</strong>
            <span>${escapeHtml(item.kind === "document" ? "문서 작업 기록" : "생성 작업 기록")} · ${escapeHtml(item.operation || item.currentChapter || "-")}</span>
          </div>
          <div>
            <span class="service-status-pill">${escapeHtml(item.status || "-")}</span>
            <small>${escapeHtml(remain)}</small>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderServiceQueue(queue) {
  const summary = queue?.summary || {};
  const items = Array.isArray(queue?.items) ? queue.items : [];
  const history = Array.isArray(queue?.history) ? queue.history : [];
  const count = Number(summary.queuedJobs || 0) + Number(summary.runningQueueJobs || 0);
  if (serviceQueueCount) {
    serviceQueueCount.textContent = `${count}건 · 최근 ${history.length}건`;
  }
  if (!serviceQueueList) return;
  const blocks = [];
  blocks.push(`
    <div class="service-queue-summary">
      <div><span>동시 실행 한도</span><strong>${escapeHtml(summary.limit ?? "-")}</strong></div>
      <div><span>실행 슬롯</span><strong>${escapeHtml(summary.occupiedSlots ?? 0)}/${escapeHtml(summary.limit ?? "-")}</strong></div>
      <div><span>대기 중</span><strong>${escapeHtml(summary.queuedJobs ?? 0)}</strong></div>
      <div><span>사용 가능</span><strong>${escapeHtml(summary.availableSlots ?? "-")}</strong></div>
    </div>
  `);
  if (items.length) {
    blocks.push(`
      <div class="service-queue-subtitle">현재 큐</div>
      ${items.slice(0, 8).map((job) => `
        <div class="service-lock-row ${job.status === "queued" ? "warning" : "done"}">
          <div>
            <strong>${escapeHtml(job.topic || job.id || "큐 작업")}</strong>
            <span>${escapeHtml(statusLabel(job.status))} · ${escapeHtml(job.currentStageLabel || job.currentStage || "실행 대기")} · ${escapeHtml(job.message || "")}</span>
          </div>
          <div>
            <span class="service-status-pill">${escapeHtml(job.writerMode || job.templateType || "-")}</span>
            <small>${escapeHtml(job.queuedAt ? formatDate(job.queuedAt) : "대기 시간 측정 중")}</small>
          </div>
        </div>
      `).join("")}
    `);
  }
  if (history.length) {
    blocks.push(`
      <div class="service-queue-subtitle">최근 큐 히스토리</div>
      ${history.slice(0, 8).map((event) => `
        <div class="service-health-item ${event.status === "queued" ? "warning" : event.status === "canceled" ? "risk" : "info"}">
          <strong>${escapeHtml(event.topic || event.stageLabel || "큐 이벤트")}</strong>
          <p>${escapeHtml(formatQueueEventLabel(event.event))} · ${escapeHtml(formatDate(event.createdAt))} · ${escapeHtml(event.message || "")}</p>
        </div>
      `).join("")}
    `);
  }
  if (!items.length && !history.length) {
    serviceQueueList.classList.add("empty");
    serviceQueueList.textContent = "현재 대기 중인 작업과 큐 히스토리가 없습니다.";
    return;
  }
  serviceQueueList.classList.remove("empty");
  serviceQueueList.innerHTML = blocks.join("");
}

function formatQueueEventLabel(event) {
  const labels = {
    job_queued: "큐 등록",
    job_started_from_queue: "실행 시작",
    job_cancel_requested: "중단 요청",
    job_canceled: "중단 완료",
    client_heartbeat_lost: "브라우저 연결 끊김",
  };
  return labels[event] || event || "큐 이벤트";
}

function renderServiceRuntime(jobs, llm) {
  const errors = llm?.recentErrors || [];
  const retries = llm?.recentRetries || [];
  const count = jobs.length + errors.length + retries.length;
  if (serviceRuntimeCount) serviceRuntimeCount.textContent = `${count}건`;
  if (!serviceRuntimeList) return;
  const blocks = [];
  for (const job of jobs.slice(0, 5)) {
    blocks.push(`
      <div class="service-health-item ${job.active ? "warning" : "info"}">
        <strong>${escapeHtml(job.topic || job.id || "진행 작업")}</strong>
        <p>${escapeHtml(job.status || "-")} · ${escapeHtml(job.currentStageLabel || job.currentStage || "단계 확인 중")} · ${escapeHtml(job.message || "")}</p>
      </div>
    `);
  }
  for (const event of errors) {
    blocks.push(`
      <div class="service-health-item risk">
        <strong>${escapeHtml(event.agent || "LLM 오류")}</strong>
        <p>${escapeHtml(event.timestamp || "")} · ${escapeHtml(event.error || "오류 상세 없음")}</p>
      </div>
    `);
  }
  for (const event of retries) {
    blocks.push(`
      <div class="service-health-item warning">
        <strong>${escapeHtml(event.agent || "LLM 재시도")}</strong>
        <p>${escapeHtml(event.timestamp || "")} · ${escapeHtml(event.error || "자동 재시도")}</p>
      </div>
    `);
  }
  if (!blocks.length) {
    serviceRuntimeList.classList.add("empty");
    serviceRuntimeList.textContent = "진행 중인 작업 또는 최근 LLM 오류가 없습니다.";
    return;
  }
  serviceRuntimeList.classList.remove("empty");
  serviceRuntimeList.innerHTML = blocks.join("");
}

function renderServiceUsage(usage) {
  const summary = usage?.summary || {};
  const recentEvents = Array.isArray(usage?.recentEvents) ? usage.recentEvents : [];
  const recentErrors = Array.isArray(usage?.recentErrors) ? usage.recentErrors : [];
  const topEvents = Array.isArray(usage?.topEvents) ? usage.topEvents : [];
  const topTargets = Array.isArray(usage?.topTargets) ? usage.topTargets : [];
  if (serviceUsageCount) {
    serviceUsageCount.textContent = `${summary.recentEvents || 0}건 · 오류 ${summary.recentErrors || 0}건`;
  }
  if (!serviceUsageList) return;
  const blocks = [];
  if (topEvents.length || topTargets.length) {
    blocks.push(`
      <div class="service-queue-summary">
        <div><span>최근 이벤트</span><strong>${escapeHtml(summary.recentEvents || 0)}</strong></div>
        <div><span>오류 경험</span><strong>${escapeHtml(summary.recentErrors || 0)}</strong></div>
        <div><span>수정/보완</span><strong>${escapeHtml(summary.revisionRequests || 0)}</strong></div>
        <div><span>주요 행동</span><strong>${escapeHtml(topEvents[0]?.name ? formatUsageEventLabel(topEvents[0].name) : "-")}</strong></div>
      </div>
    `);
  }
  if (topTargets.length) {
    blocks.push(`
      <div class="service-queue-subtitle">자주 다룬 문서/주제</div>
      ${topTargets.slice(0, 5).map((item) => `
        <div class="service-health-item info">
          <strong>${escapeHtml(item.name || "-")}</strong>
          <p>${escapeHtml(item.count || 0)}회 기록됨</p>
        </div>
      `).join("")}
    `);
  }
  if (recentErrors.length) {
    blocks.push(`
      <div class="service-queue-subtitle">최근 오류 경험</div>
      ${recentErrors.slice(0, 4).map((event) => renderServiceUsageEvent(event, "risk")).join("")}
    `);
  }
  if (recentEvents.length) {
    blocks.push(`
      <div class="service-queue-subtitle">최근 사용자 행동</div>
      ${recentEvents.slice(0, 8).map((event) => renderServiceUsageEvent(event, event.event === "ui_error" ? "risk" : "info")).join("")}
    `);
  }
  if (!blocks.length) {
    serviceUsageList.classList.add("empty");
    serviceUsageList.textContent = "아직 수집된 사용자 행동 로그가 없습니다.";
    return;
  }
  serviceUsageList.classList.remove("empty");
  serviceUsageList.innerHTML = blocks.join("");
}

function renderServiceUsageEvent(event, tone = "info") {
  return `
    <div class="service-health-item ${tone}">
      <strong>${escapeHtml(formatUsageEventLabel(event.event))}${event.title ? ` · ${escapeHtml(event.title)}` : ""}</strong>
      <p>${escapeHtml(formatDate(event.timestamp))}${event.summary ? ` · ${escapeHtml(event.summary)}` : ""}</p>
    </div>
  `;
}

function formatUsageEventLabel(event) {
  const labels = {
    policy_create_requested: "문서 작성 요청",
    policy_create_completed: "문서 작성 완료",
    policy_create_error: "문서 작성 오류",
    policy_create_failed: "문서 작성 실패",
    revision_requested: "보완 요청",
    revision_completed: "보완 완료",
    revision_error: "보완 오류",
    manual_review_response: "수동 검토 응답",
    manual_edit_started: "직접 편집 시작",
    manual_edit_saved: "직접 편집 저장",
    manual_edit_failed: "직접 편집 실패",
    html_uploaded: "HTML 업로드",
    html_upload_failed: "HTML 업로드 실패",
    json_uploaded: "JSON 업로드",
    json_upload_failed: "JSON 업로드 실패",
    document_qa_review_started: "개발/QA 검수 시작",
    document_qa_review_completed: "개발/QA 검수 완료",
    document_qa_review_failed: "개발/QA 검수 실패",
    ui_error: "화면 오류",
    policy_selected: "문서 선택",
    topic_selected_for_request: "작성 주제 선택",
    llm_mode_changed: "LLM 모드 변경",
  };
  return labels[event] || event || "사용 이벤트";
}

function renderDashboardPolicyStatus() {
  const topics = getTopicOptions();
  const completedTopicKeys = new Set();
  const inProgressPolicyKeys = new Set();
  const draftTopicKeys = new Set();
  for (const topic of topics) {
    const topicKey = normalizeTopic(topic);
    const item = latestItemForTopic(topic);
    if (item) {
      if (isPolicyCompleted(item)) {
        completedTopicKeys.add(topicKey);
      } else {
        inProgressPolicyKeys.add(topicKey);
      }
      continue;
    }
    if (latestDraftForTopic(topic)) {
      draftTopicKeys.add(topicKey);
    }
  }
  const total = topics.length;
  const completed = completedTopicKeys.size;
  const drafting = inProgressPolicyKeys.size + draftTopicKeys.size;
  const todo = Math.max(0, total - completed - drafting);

  setDashboardNumber(dashboardTotalPolicies, total);
  setDashboardNumber(dashboardDraftPolicies, drafting);
  setDashboardNumber(dashboardCompletedPolicies, completed);
  setDashboardNumber(dashboardTodoPolicies, todo);
}

function renderAgentDashboard(agentData, errorMessage = "") {
  if (!agentDashboardRows) return;
  if (!agentData) {
    if (agentDashboardMeta) agentDashboardMeta.textContent = errorMessage || "Agent 호출 로그를 불러오지 못했습니다.";
    if (agentTotalCalls) agentTotalCalls.textContent = "-";
    if (agentTotalTokens) agentTotalTokens.textContent = "-";
    if (agentTotalCost) agentTotalCost.textContent = "-";
    if (agentDiskUsage) agentDiskUsage.textContent = "-";
    agentDashboardRows.innerHTML = '<tr><td colspan="3">Agent 사용량을 확인할 수 없습니다.</td></tr>';
    return;
  }

  const summary = agentData.summary || {};
  const rows = Array.isArray(agentData.items) ? agentData.items : [];
  const maxTokens = Math.max(1, ...rows.map((row) => Number(row.totalTokens || 0)));
  if (agentDashboardMeta) {
    const sourceLabel = summary.usageSource === "openai_api" ? "OpenAI API 기준" : "로컬 로그 기준";
    const statusLabel = openAiUsageStatusLabel(summary.externalUsageStatus);
    const statusNote = statusLabel ? ` · ${statusLabel}` : "";
    agentDashboardMeta.textContent = summary.lastUpdated
      ? `${sourceLabel} · 최근 업데이트 ${formatDate(summary.lastUpdated)}${statusNote}`
      : `${sourceLabel} · 아직 집계된 LLM 호출이 없습니다.${statusNote}`;
    if (summary.externalUsageMessage || summary.externalUsageDetail || summary.costBasis) {
      agentDashboardMeta.title = [summary.externalUsageMessage, summary.externalUsageDetail, summary.costBasis]
        .filter(Boolean)
        .join("\n");
    } else {
      agentDashboardMeta.removeAttribute("title");
    }
  }
  if (agentTotalCalls) agentTotalCalls.textContent = formatNumber(summary.calls || 0);
  if (agentTotalTokens) agentTotalTokens.textContent = formatCompactNumber(summary.totalTokens || 0);
  if (agentTotalCost) agentTotalCost.textContent = formatUsdCost(summary.estimatedCostUsd);
  if (agentDiskUsage) agentDiskUsage.textContent = formatSize(summary.diskUsageBytes);
  if (rows.length === 0) {
    agentDashboardRows.innerHTML = '<tr><td colspan="3">아직 Agent 호출 기록이 없습니다.</td></tr>';
    return;
  }

  agentDashboardRows.innerHTML = rows
    .map((row) => {
      const ratio = Math.max(6, Math.round((Number(row.totalTokens || 0) / maxTokens) * 100));
      const modelLabel = modelSummary(row.models || {});
      return `
        <tr>
          <td class="agent-cell">
            <strong>${escapeHtml(row.agent || "-")}</strong>
            <span>${escapeHtml(modelLabel)}</span>
          </td>
          <td class="calls-cell">
            <span class="metric-pill"><b>${escapeHtml(formatNumber(row.calls || 0))}</b><small>호출</small></span>
          </td>
          <td class="tokens-cell">
            <div class="token-usage-line">
              <div class="token-meter" aria-label="${escapeHtml(formatNumber(row.totalTokens || 0))} tokens">
                <i style="width: ${ratio}%"></i>
              </div>
              <b>${escapeHtml(formatCompactNumber(row.totalTokens || 0))}</b>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function openAiUsageStatusLabel(status) {
  switch (status) {
    case "ok":
      return "OpenAI 집계 연결됨";
    case "not_configured":
      return "OpenAI 집계 미설정";
    case "disabled":
      return "OpenAI 집계 비활성화";
    case "permission_denied":
      return "OpenAI 집계 권한 없음";
    case "auth_failed":
      return "OpenAI 집계 인증 실패";
    case "network_error":
      return "OpenAI 집계 연결 지연";
    case "error":
      return "OpenAI 집계 연결 실패";
    default:
      return "";
  }
}

function setDashboardNumber(element, value) {
  if (element) element.textContent = formatNumber(value);
}

function modelSummary(models) {
  const entries = Object.entries(models || {}).sort((left, right) => Number(right[1]) - Number(left[1]));
  if (entries.length === 0) return "호출 없음";
  const [model, count] = entries[0];
  const extra = entries.length > 1 ? ` 외 ${entries.length - 1}` : "";
  return `${model} · ${formatNumber(count)}회${extra}`;
}

function openProgressModal(job) {
  if (job?.id && currentProgressJob?.id && currentProgressJob.id !== job.id) {
    liveFeedbackCache.clear();
    liveFeedbackInFlight.clear();
  }
  progressModal.hidden = false;
  progressError.hidden = true;
  progressError.innerHTML = "";
  renderProgress(job);
}

function progressDisplayText(value) {
  return String(value || "").replaceAll("정책서", "문서");
}

function progressStageDisplayName(job, currentStage) {
  const label = progressDisplayText(currentStage?.label || statusLabel(job?.status));
  const status = currentStage?.status || job?.status;
  if (!currentStage) return label;
  if (status === "review") return `${label} 사용자 검수 대기`;
  if (status === "done") return `${label} 완료`;
  if (["running", "retry", "canceling"].includes(status)) return `${label} 진행 중`;
  return label;
}

function progressTitleLabel(job) {
  const kind = job?.kind === "revision" ? "보완" : "작성";
  switch (job?.status) {
    case "queued":
      return `문서 ${kind} 대기 중입니다.`;
    case "waiting_review":
      return "사용자 검수를 기다리고 있습니다.";
    case "completed":
      return `문서 ${kind}이 완료되었습니다.`;
    case "canceled":
    case "cancelled":
      return `문서 ${kind}이 중단되었습니다.`;
    case "canceling":
      return `문서 ${kind}을 중단하고 있습니다.`;
    case "error":
      return `문서 ${kind} 중 오류가 발생했습니다.`;
    default:
      return `문서를 ${kind}하고 있습니다.`;
  }
}

function isProgressBusy(job) {
  return ["queued", "running", "retry", "canceling"].includes(String(job?.status || ""));
}

function renderProgress(job) {
  if (!job) return;
  currentProgressJob = job;
  const currentStage = (job.stages || []).find((stage) => stage.key === job.currentStageKey);
  const activity = Array.isArray(job.activity) ? job.activity : [];
  progressModal.dataset.status = String(job.status || "unknown");
  progressModal.dataset.busy = isProgressBusy(job) ? "true" : "false";
  if (progressCancelButton) {
    const canCancel = isCancelableJob(job);
    progressCancelButton.hidden = !canCancel;
    progressCancelButton.disabled = !canCancel || job.status === "canceling";
  }
  if (progressTitle) {
    progressTitle.textContent = progressTitleLabel(job);
  }
  if (progressPolicyTarget) {
    progressPolicyTarget.textContent = progressDisplayText(progressTargetLabel(job));
  }
  progressMessage.textContent = progressDisplayText(job.message || "문서를 작성하고 있습니다.");
  totalElapsed.textContent = formatDuration(job.elapsedMs || 0);
  if (currentStageElapsed) currentStageElapsed.textContent = formatDuration(currentStage?.durationMs || 0);
  currentStageName.textContent = progressStageDisplayName(job, currentStage);
  jobStatus.textContent = statusLabel(job.status);
  renderProgressFocus(job, currentStage, activity);
  renderProgressActivity(job, currentStage);
  renderManualReview(job);

  if (progressStepCount) {
    const doneCount = (job.stages || []).filter((stage) => stage.status === "done").length;
    progressStepCount.textContent = `${doneCount}/${(job.stages || []).length}`;
  }
  progressSteps.innerHTML = (job.stages || [])
    .map((stage, index) => `
      <div class="progress-step ${escapeHtml(stage.status)}">
        <div class="step-index">${String(index + 1).padStart(2, "0")}</div>
        <div class="step-body">
          <div class="step-title">
            <strong>${escapeHtml(stage.label)}</strong>
            <span>${stage.attempt ? `${stage.attempt}회차` : ""}</span>
          </div>
          <div class="step-meta">
            <span>${statusLabel(stage.status)}</span>
            <span>${formatDuration(stage.durationMs || 0)}</span>
            ${stage.score !== null && stage.score !== undefined ? `<span>${escapeHtml(stage.score)}점</span>` : ""}
          </div>
        </div>
      </div>
    `)
    .join("");

  if (job.status === "error") {
    progressError.hidden = false;
    const errorText = progressDisplayText(job.error || job.message || "문서 생성 중 오류가 발생했습니다.");
    progressError.innerHTML = `
      <span>${escapeHtml(errorText)}</span>
      ${canContinueFailedRevision(job) ? `
        <button class="progress-error-continue-button" type="button" data-progress-error-continue>
          계속 진행
        </button>
      ` : ""}
    `;
    progressError.querySelector("[data-progress-error-continue]")?.addEventListener("click", () => {
      continueFailedRevision(job.id);
    });
  } else {
    progressError.hidden = true;
    progressError.innerHTML = "";
  }
}

function canContinueFailedRevision(job) {
  return Boolean(
    job?.id &&
      job?.kind === "revision" &&
      job?.status === "error" &&
      job?.pendingRevisionSave?.available
  );
}

async function continueFailedRevision(jobId) {
  if (!jobId) return;
  if (!guardWritePermission("조회 권한은 기준 미달 수정본 저장을 실행할 수 없습니다.")) return;
  const button = progressError?.querySelector("[data-progress-error-continue]");
  if (button) {
    button.disabled = true;
    button.textContent = "저장 중";
  }
  try {
    const response = await fetch(apiPath(`/api/jobs/${encodeURIComponent(jobId)}/review`), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({ action: "continue" })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "수정본 저장을 계속 진행하지 못했습니다.");
    }
    activeJobId = data.job?.id || jobId;
    renderProgress(data.job);
    setMessage("Inspector 기준 미달을 확인하고 수정본을 새 버전으로 저장했습니다.");
    await loadPolicies(data.job?.result?.name || "", { silent: true });
  } catch (error) {
    setMessage(error.message || "수정본 저장 계속 진행 중 오류가 발생했습니다.", true);
    if (button) {
      button.disabled = false;
      button.textContent = "계속 진행";
    }
  }
}

function renderProgressFocus(job, currentStage, activity) {
  const stages = Array.isArray(job.stages) ? job.stages : [];
  const progress = progressPercent(stages, job.status);
  if (progressOverallPercent) progressOverallPercent.textContent = `${progress}%`;
  if (progressOverallBar) progressOverallBar.style.width = `${progress}%`;
  if (progressFocusDescription) {
    progressFocusDescription.textContent = progressDisplayText(
      currentStage?.message || job.message || "Agent가 현재 단계의 산출물을 작성하고 있습니다."
    );
  }
  if (progressEta) progressEta.textContent = estimatedRemainingLabel(job, progress);
  if (progressGate) {
    progressGate.textContent = gateStatusLabel(currentStage);
    progressGate.className = currentStage?.score !== null && currentStage?.score !== undefined ? "gate-score" : "";
  }

  renderLifeFeedback(job, currentStage, activity, progress);
  renderInlineList(progressCurrentWorkList, currentWorkItems(job, currentStage, activity));
  renderInlineList(progressGateList, stageGateItems(currentStage));
  renderNextStages(progressNextList, stages, currentStage);
  renderInspectorNotes(activity, currentStage);
}

function progressPercent(stages, status) {
  if (!stages.length) return status === "completed" ? 100 : 0;
  const completedWeight = stages.reduce((sum, stage) => {
    if (stage.status === "done") return sum + 1;
    if (["running", "retry", "review", "canceling"].includes(stage.status)) return sum + 0.45;
    return sum;
  }, 0);
  if (status === "completed") return 100;
  return Math.max(0, Math.min(99, Math.round((completedWeight / stages.length) * 100)));
}

function estimatedRemainingLabel(job, progress) {
  const elapsed = Number(job?.elapsedMs || 0);
  if (!elapsed || progress <= 5 || progress >= 100) return progress >= 100 ? "완료" : "측정 중";
  const remainingMs = Math.max(0, Math.round((elapsed / progress) * (100 - progress)));
  return `약 ${formatDuration(remainingMs)} 후`;
}

function gateStatusLabel(stage) {
  if (!stage) return "검수 대기";
  if (stage.score !== null && stage.score !== undefined) {
    return `${stage.score}점`;
  }
  if (stage.status === "retry") return "보완 중";
  if (stage.status === "review") return "사용자 검수";
  if (stage.status === "done") return "통과";
  return "검수 대기";
}

function currentWorkItems(job, currentStage, activity) {
  const artifacts = collectProgressArtifacts(job, activity).filter((item) => isHtmlArtifact(item.artifact));
  const items = [
    currentStage?.label ? `단계: ${currentStage.label}` : "",
    currentStage?.attempt ? `시도: ${currentStage.attempt}회차` : "",
    job?.message ? `작업: ${job.message}` : "",
    artifacts.length ? `중간 HTML: ${artifacts.length}개 저장` : "중간 HTML: 저장 대기",
  ];
  return items.filter(Boolean).slice(0, 5);
}

function stageGateItems(stage) {
  const label = String(stage?.label || stage?.name || "").toLowerCase();
  if (label.includes("process") || label.includes("프로세스")) {
    return ["유즈케이스와 연결성", "업무 흐름의 완결성", "기능·정책 연결 준비", "예외 흐름 포함 여부"];
  }
  if (label.includes("function") || label.includes("기능")) {
    return ["프로세스별 필요 기능", "세부 기능 구성 적정성", "기능과 정책 역할 분리", "누락 기능 여부"];
  }
  if (label.includes("polic") || label.includes("정책")) {
    return ["정책값·조건 구체성", "정책 항목 단위 적정성", "프로세스 필요 정책 충족", "TBD 사유 명확성"];
  }
  if (label.includes("state") || label.includes("상태")) {
    return ["액터·유즈케이스 기반 상태", "전이 이벤트 유즈케이스 사용", "현재/다음 상태 정합성", "예외·제한 상태 포함"];
  }
  if (label.includes("usecase") || label.includes("유즈")) {
    return ["액터별 업무 목표", "프로세스 대상 여부", "과도한 세분화 방지", "상태 도출 가능성"];
  }
  return ["템플릿 구조 준수", "샘플 수준 정렬", "이전 장과 정합성", "간결한 정책서 문체"];
}

function renderInlineList(target, items) {
  if (!target) return;
  target.innerHTML = (items.length ? items : ["표시할 항목이 없습니다."])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
}

function renderNextStages(target, stages, currentStage) {
  if (!target) return;
  const currentIndex = stages.findIndex((stage) => stage.key === currentStage?.key);
  const next = stages
    .slice(currentIndex >= 0 ? currentIndex + 1 : 0)
    .filter((stage) => stage.status === "pending")
    .slice(0, 3);
  target.innerHTML = (next.length ? next : [{ label: "최종 저장", status: "pending" }])
    .map((stage) => `<li><span>${escapeHtml(stage.label || "다음 단계")}</span></li>`)
    .join("");
}

function renderLifeFeedback(job, currentStage, activity, progress) {
  if (!progressLifeFeedbackList) return;
  let messages = [];
  try {
    messages = lifeFeedbackMessages(job || {}, currentStage || null, Array.isArray(activity) ? activity : [], progress);
  } catch (error) {
    messages = [
      {
        label: "NOVA",
        tone: "info",
        text: "진행 상태를 확인하고 있어요. LLM 토큰이나 인증키가 없어도 이 안내 영역은 기본 진행 정보로 계속 표시됩니다.",
      },
    ];
  }
  if (!messages.length) {
    messages = [
      {
        label: "NOVA",
        tone: "info",
        text: "진행 정보를 기다리고 있어요. 단계가 시작되면 여기에서 바로 알려드릴게요.",
      },
    ];
  }
  const event = buildLiveFeedbackEvent(job || {}, currentStage || null, Array.isArray(activity) ? activity : [], progress, messages);
  const llmMessage = event ? liveFeedbackCache.get(event.key) : null;
  if (llmMessage) {
    messages = [llmMessage, ...messages.filter((item) => item.label !== "NOVA").slice(0, 3)];
  } else if (event) {
    requestLiveFeedback(event, job || {});
  }
  progressLifeFeedbackList.innerHTML = messages
    .map((item) => `
      <div class="life-feedback-bubble ${escapeHtml(item.tone || "info")}">
        <span>${escapeHtml(item.label || "NOVA")}</span>
        <p>${escapeHtml(item.text)}</p>
      </div>
    `)
    .join("");
  if (progressLifeFeedbackTone) {
    progressLifeFeedbackTone.textContent = lifeFeedbackToneLabel(job, currentStage);
  }
}

function buildLiveFeedbackEvent(job, currentStage, activity, progress, localMessages) {
  if (!job?.id) return null;
  const eventType = liveFeedbackEventType(job, currentStage);
  if (!eventType) return null;
  const stageKey = currentStage?.key || "none";
  const attempt = currentStage?.attempt || 0;
  const scoreKey = currentStage?.score !== null && currentStage?.score !== undefined ? `score-${currentStage.score}` : "score-none";
  const key = [job.id, eventType, job.status || "unknown", stageKey, attempt, scoreKey].join(":");
  const artifacts = collectProgressArtifacts(job || {}, activity || []).filter((item) => isHtmlArtifact(item.artifact));
  const recentActivity = (activity || [])
    .slice(-3)
    .map((item) => progressDisplayText(String(item.message || item.event || item.type || "")))
    .filter(Boolean);
  return {
    key,
    payload: {
      eventType,
      topic: job.topic || job.name || "",
      status: job.status || "",
      progress,
      currentStage: {
        key: currentStage?.key || "",
        label: progressDisplayText(currentStage?.label || ""),
        status: currentStage?.status || "",
        score: currentStage?.score ?? "",
        attempt,
        message: progressDisplayText(currentStage?.message || job.message || ""),
      },
      artifactCount: artifacts.length,
      localMessages: (localMessages || []).slice(0, 3).map((item) => progressDisplayText(item.text || "")),
      recentActivity,
    },
  };
}

function liveFeedbackEventType(job, currentStage) {
  if (job?.status === "completed") return "completed";
  if (job?.status === "error") return "error";
  if (job?.status === "waiting_review" || currentStage?.status === "review") return "manual_review";
  if (currentStage?.score !== null && currentStage?.score !== undefined) return "inspection_score";
  if (currentStage?.status === "retry" || job?.status === "retry") return "revision_retry";
  if (currentStage?.status === "running") return "stage_started";
  if (job?.status === "queued") return "queued";
  return "";
}

function canRequestLiveFeedback(job) {
  const mode = job?.writerMode || "";
  return mode === "llm" && (getSiteWriterMode() === "llm" || (llmAccessAuthorized && Boolean(llmAccessToken)));
}

function requestLiveFeedback(event, job) {
  if (!event?.key || !canRequestLiveFeedback(job)) return;
  if (liveFeedbackCache.has(event.key) || liveFeedbackInFlight.has(event.key)) return;

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 15000);
  liveFeedbackInFlight.set(event.key, true);

  fetch(apiPath("/api/live-feedback"), {
    method: "POST",
    headers: jsonHeaders(),
    signal: controller.signal,
    body: JSON.stringify(
      withClientSession({
        writerMode: "llm",
        llmAccessToken,
        event: event.payload,
      })
    ),
  })
    .then(async (response) => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok || !data.message) return;
      liveFeedbackCache.set(event.key, {
        label: "NOVA",
        tone: data.tone || "info",
        text: progressDisplayText(data.message),
      });
      if (currentProgressJob?.id === job?.id) {
        renderProgress(currentProgressJob);
      }
    })
    .catch(() => {
      // Live feedback must never interrupt document generation; local messages remain visible.
    })
    .finally(() => {
      window.clearTimeout(timeoutId);
      liveFeedbackInFlight.delete(event.key);
    });
}

function lifeFeedbackMessages(job, currentStage, activity, progress) {
  const stages = Array.isArray(job?.stages) ? job.stages : [];
  const safeProgress = Number.isFinite(Number(progress)) ? Math.max(0, Math.min(100, Math.round(Number(progress)))) : 0;
  const artifacts = collectProgressArtifacts(job || {}, Array.isArray(activity) ? activity : []).filter((item) => isHtmlArtifact(item.artifact));
  const currentLabel = progressDisplayText(currentStage?.label || "현재 단계");
  const currentMessage = progressDisplayText(currentStage?.message || job?.message || "문서 작성을 준비하고 있습니다.");
  const nextStage = nextPendingStage(stages, currentStage);
  const messages = [];

  if (job?.status === "queued") {
    messages.push({
      label: "NOVA",
      tone: "info",
      text: "작업 순서를 잡고 있어요. 앞 작업이 끝나면 바로 이어서 시작합니다.",
    });
  } else if (job?.status === "waiting_review") {
    messages.push({
      label: "NOVA",
      tone: "review",
      text: "잠시 멈춰서 사용자 검수를 기다리고 있어요. 아래 검수 패널에서 이어서 작성하거나 다시 작성할 수 있습니다.",
    });
  } else if (job?.status === "completed") {
    messages.push({
      label: "NOVA",
      tone: "done",
      text: "문서 작성이 끝났어요. 이제 문서 작업실에서 미리보기, 구조 분석, 개발/QA 검수를 이어갈 수 있습니다.",
    });
  } else if (job?.status === "error") {
    messages.push({
      label: "NOVA",
      tone: "warn",
      text: "진행 중 오류가 발생했어요. 마지막 체크포인트가 있으면 그 지점부터 다시 이어갈 수 있게 준비해둘게요.",
    });
  } else {
    messages.push({
      label: "NOVA",
      tone: "info",
      text: `${currentLabel} 단계를 진행하고 있어요. ${currentMessage}`,
    });
  }

  if (currentStage?.score !== null && currentStage?.score !== undefined) {
    messages.push({
      label: "Inspector",
      tone: Number(currentStage.score) >= 85 ? "done" : "warn",
      text: `방금 검수 점수는 ${currentStage.score}점입니다. 기준에 못 미치면 같은 장에서 보완하고, 반복되면 다음 단계와 최종 검수로 이슈를 넘깁니다.`,
    });
  } else if (["running", "retry", "canceling"].includes(job?.status)) {
    messages.push({
      label: "NOVA",
      tone: "info",
      text: `전체 진행률은 ${safeProgress}%예요. 아직 점수는 없고, 먼저 JSON 구조와 중간 HTML을 안정적으로 만드는 중입니다.`,
    });
  }

  if (artifacts.length) {
    messages.push({
      label: "HTML",
      tone: "done",
      text: `중간 HTML ${artifacts.length}개가 저장됐어요. 오른쪽 Live Output에서 방금 만든 화면을 바로 열어볼 수 있습니다.`,
    });
  } else {
    messages.push({
      label: "HTML",
      tone: "info",
      text: "첫 장이 완료되면 중간 HTML을 저장해서 오른쪽에 보여드릴게요.",
    });
  }

  if (nextStage && !["completed", "error", "waiting_review"].includes(job?.status)) {
    messages.push({
      label: "Next",
      tone: "info",
      text: `이 단계가 정리되면 ${nextStage.label || "다음 단계"}로 넘어갈 예정입니다.`,
    });
  }

  return messages.slice(0, 4);
}

function nextPendingStage(stages, currentStage) {
  const currentIndex = stages.findIndex((stage) => stage.key === currentStage?.key);
  return stages
    .slice(currentIndex >= 0 ? currentIndex + 1 : 0)
    .find((stage) => stage.status === "pending");
}

function lifeFeedbackToneLabel(job, currentStage) {
  if (job?.status === "waiting_review" || currentStage?.status === "review") return "검수 대기";
  if (job?.status === "error") return "확인 필요";
  if (job?.status === "completed") return "완료";
  if (currentStage?.status === "retry") return "보완 중";
  if (currentStage?.score !== null && currentStage?.score !== undefined) return `${currentStage.score}점`;
  return "실시간";
}

function renderInspectorNotes(activity, currentStage) {
  if (!progressInspectorNotes) return;
  const notes = [];
  if (currentStage?.score !== null && currentStage?.score !== undefined) {
    notes.push({
      tier: currentStage.score >= 90 ? "P3" : currentStage.score >= 85 ? "P2" : "P1",
      text: progressDisplayText(`${currentStage.label || "현재 단계"} Inspector 점수 ${currentStage.score}점`),
    });
  }
  [...(activity || [])].reverse().some((item) => {
    const previewItems = Array.isArray(item.preview?.items) ? item.preview.items : [];
    previewItems.forEach((text) => {
      if (notes.length < 4 && text) {
        notes.push({ tier: noteTierFromText(String(text)), text: progressDisplayText(String(text)) });
      }
    });
    return notes.length >= 4;
  });
  if (progressInspectorCount) progressInspectorCount.textContent = `${notes.length}건`;
  progressInspectorNotes.innerHTML = notes.length
    ? notes
        .slice(0, 4)
        .map((note) => `
          <div class="inspector-note">
            <span class="${escapeHtml(note.tier)}">${escapeHtml(note.tier)}</span>
            <p>${escapeHtml(note.text)}</p>
          </div>
        `)
        .join("")
    : '<div class="inspector-note muted">아직 표시할 검수 메모가 없습니다.</div>';
}

function noteTierFromText(text) {
  if (/실패|오류|미통과|기준 미달|Critical|P1/i.test(text)) return "P1";
  if (/보완|확인|누락|정합|P2/i.test(text)) return "P2";
  return "P3";
}

function renderProgressActivity(job, currentStage) {
  const activity = Array.isArray(job.activity) ? job.activity : [];
  const latestCheckpoint =
    [...activity].reverse().find((item) => item.checkpoint)?.checkpoint ||
    (job.stages || []).slice().reverse().find((stage) => stage.checkpoint)?.checkpoint ||
    job.checkpoint;

  const htmlArtifacts = collectProgressArtifacts(job, activity)
    .filter((item) => isHtmlArtifact(item.artifact))
    .slice(-10)
    .reverse();
  const latestHtml = htmlArtifacts[0];

  if (progressActivityTitle) {
    progressActivityTitle.textContent = "중간 HTML 확인";
  }
  if (progressActivityMeta) {
    progressActivityMeta.textContent = htmlArtifacts.length
      ? `${htmlArtifacts.length}개 HTML 스냅샷 저장됨`
      : "각 장이 완료되면 HTML 파일이 여기에 표시됩니다.";
  }
  if (progressActivityMessage) {
    progressActivityMessage.hidden = true;
    progressActivityMessage.textContent = "";
  }

  if (!progressArtifactList) return;
  if (!htmlArtifacts.length) {
    progressArtifactList.innerHTML = "";
    progressArtifactList.innerHTML = `
      <section class="artifact-section" aria-label="중간 HTML 확인">
        <div class="artifact-section-head">
          <div>
            <span>중간 HTML 확인</span>
            <strong>저장 대기 중</strong>
          </div>
        </div>
        <div class="artifact-empty">각 장이 완료되면 여기에서 단계별 HTML 파일을 바로 열어볼 수 있습니다.</div>
      </section>
      ${job.status === "error" && latestCheckpoint ? `
        <button id="resumeCheckpointButton" class="resume-checkpoint-button" type="button">
          마지막 체크포인트부터 재개
        </button>
      ` : ""}
    `;
    progressArtifactList.querySelector("#resumeCheckpointButton")?.addEventListener("click", () => {
      resumeFromCheckpoint(latestCheckpoint);
    });
    return;
  }

  progressArtifactList.innerHTML = [
    `
      <section class="artifact-section" aria-label="중간 HTML 확인">
        <div class="artifact-section-head">
          <div>
            <span>중간 HTML 확인</span>
            <strong>${htmlArtifacts.length ? `${htmlArtifacts.length}개 스냅샷` : "저장 대기 중"}</strong>
          </div>
          ${latestHtml ? `
            <a class="artifact-primary" href="${escapeHtml(latestHtml.artifact.url)}" target="_blank" rel="noreferrer">
              최근 HTML 열기
            </a>
          ` : ""}
        </div>
        <div class="artifact-stack">
          ${htmlArtifacts.length ? htmlArtifacts.map((item) => `
            <a class="artifact-link html-snapshot" href="${escapeHtml(item.artifact.url)}" target="_blank" rel="noreferrer">
              <span>${escapeHtml(progressDisplayText(item.stageLabel || "단계별 HTML"))}</span>
              <strong>${escapeHtml(progressDisplayText(item.artifact.name || "HTML snapshot"))}</strong>
            </a>
          `).join("") : `
            <div class="artifact-empty">각 장이 완료되면 여기에서 단계별 HTML 파일을 바로 열어볼 수 있습니다.</div>
          `}
        </div>
      </section>
    `,
    job.status === "error" && latestCheckpoint ? `
      <button id="resumeCheckpointButton" class="resume-checkpoint-button" type="button">
        마지막 체크포인트부터 재개
      </button>
    ` : "",
  ].join("");
  progressArtifactList.querySelector("#resumeCheckpointButton")?.addEventListener("click", () => {
    resumeFromCheckpoint(latestCheckpoint);
  });
}

function progressTargetLabel(job) {
  const topic = String(job?.topic || "").trim() || "선택한 주제";
  const templateLabel = job?.templateType === "full" ? "Full 버전" : "간소화 버전";
  const workLabel = job?.kind === "revision" ? "수정/보완 중" : "초안 작성 중";
  return `작성 대상 · ${topic} 문서 · ${templateLabel} · ${workLabel}`;
}

function collectProgressArtifacts(job, activity = []) {
  const collected = [];
  const pushArtifact = (artifact, source = {}) => {
    if (!artifact || typeof artifact !== "object") return;
    const url = String(artifact.url || "").trim();
    const name = String(artifact.name || "").trim();
    if (!url && !name) return;
    collected.push({
      artifact,
      stageLabel: source.stageLabel || source.label || "단계별 HTML",
      createdAt: source.createdAt || source.finishedAt || source.startedAt || "",
      key: url || String(artifact.path || "") || name,
    });
  };

  (activity || []).forEach((item) => pushArtifact(item.artifact, item));
  (job?.stages || []).forEach((stage) => pushArtifact(stage.artifact, stage));
  if (job?.result?.url || job?.result?.name) {
    pushArtifact(
      { url: job.result.url, name: job.result.name, path: job.result.name },
      { stageLabel: "최종 HTML", createdAt: job.finishedAt }
    );
  }

  const deduped = new Map();
  collected.forEach((item) => {
    deduped.set(item.key, item);
  });
  return Array.from(deduped.values());
}

function isHtmlArtifact(artifact) {
  const name = String(artifact?.name || artifact?.path || artifact?.url || "").toLowerCase();
  return name.endsWith(".html") || name.includes(".html?");
}

async function resumeFromCheckpoint(checkpoint) {
  if (!checkpoint || !currentProgressJob) return;
  closeProgressPolling();
  setMessage("마지막 체크포인트부터 정책서 생성을 재개합니다.");
  await startResumeRequest({
    topic: currentProgressJob.topic,
    templateType: currentProgressJob.templateType || "simple",
    reviewMode: currentProgressJob.reviewMode || "auto",
    inspectionMode: currentProgressJob.inspectionMode || "chapter-final",
    writerMode: getSelectedWriterMode(),
    checkpointPath: checkpoint.path,
  });
}

async function resumeDraft(draft) {
  if (!draft?.checkpoint?.path && !draft?.resumeFrom) return;
  closeProgressPolling();
  setMessage("보관된 중간 결과부터 정책서 생성을 이어서 진행합니다.");
  await startResumeRequest({
    topic: draft.topic,
    templateType: draft.templateType || "simple",
    reviewMode: draft.reviewMode || "auto",
    inspectionMode: draft.inspectionMode || "chapter-final",
    writerMode: getSelectedWriterMode(),
    checkpointPath: draft.resumeFrom || draft.checkpoint.path,
  });
}

async function startResumeRequest({ topic, templateType, reviewMode, inspectionMode = "chapter-final", writerMode = "mock", checkpointPath, brief = "" }) {
  if (!topic || !checkpointPath) return;
  if (!guardWritePermission("조회 권한은 작성 재개를 실행할 수 없습니다.")) return;
  if (resumeDraftButton) resumeDraftButton.disabled = true;
  try {
    const allowed = await ensureWriterModeAccess(writerMode || "mock");
    if (!allowed) {
      if (resumeDraftButton) resumeDraftButton.disabled = false;
      return;
    }
    const response = await fetch(apiPath("/api/policies"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({
        topic,
        templateType: templateType || "simple",
        reviewMode: reviewMode || "auto",
        inspectionMode: inspectionMode || "chapter-final",
        writerMode: writerMode || "mock",
        llmAccessToken: writerMode === "llm" ? llmAccessToken : "",
        resumeFrom: checkpointPath,
        brief,
        author: document.querySelector("#author")?.value || "Policy Web",
      })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "체크포인트 재개에 실패했습니다.");
    }
    activeJobId = data.job.id;
    openProgressModal(data.job);
    startProgressPolling(activeJobId);
  } catch (error) {
    setMessage(error.message, true);
    if (resumeDraftButton) resumeDraftButton.disabled = false;
    if (revisionButton) revisionButton.disabled = false;
  }
}

function openFullVersionModal() {
  if (!canCreateFullVersionFromSelectedPolicy()) {
    setMessage("Full 버전 작성은 작성 완료된 간소화 문서에서만 시작할 수 있습니다.", true);
    return;
  }
  if (!fullVersionModal) return;
  const autoMode = fullVersionModal.querySelector('input[name="fullVersionReviewMode"][value="auto"]');
  const chapterFinal = fullVersionModal.querySelector('input[name="fullVersionInspectionMode"][value="chapter-final"]');
  if (autoMode) autoMode.checked = true;
  if (chapterFinal) chapterFinal.checked = true;
  fullVersionModal.hidden = false;
  fullVersionStartButton?.focus();
}

function closeFullVersionModal() {
  if (fullVersionModal) fullVersionModal.hidden = true;
}

function selectedFullVersionOption(name, fallback) {
  return fullVersionModal?.querySelector(`input[name="${name}"]:checked`)?.value || fallback;
}

async function startFullVersionFromSimplePolicy() {
  if (!guardWritePermission("조회 권한은 Full 버전 작성을 실행할 수 없습니다.")) return;
  if (!guardPolicyAdminAction("Full 버전 전환은 관리자만 실행할 수 있습니다.")) return;
  const item = selectedPolicyItem();
  if (!item || !canCreateFullVersionFromSelectedPolicy()) {
    setMessage("Full 버전 작성은 작성 완료된 간소화 문서에서만 시작할 수 있습니다.", true);
    return;
  }
  const writerMode = getSelectedWriterMode();
  if (fullVersionStartButton) fullVersionStartButton.disabled = true;
  try {
    const allowed = await ensureWriterModeAccess(writerMode || "mock");
    if (!allowed) return;
    const response = await fetch(apiPath("/api/policies/full-from-simple"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(
        withClientSession({
          name: item.name,
          sourceName: item.name,
          topic: item.topic,
          reviewMode: selectedFullVersionOption("fullVersionReviewMode", "auto"),
          inspectionMode: selectedFullVersionOption("fullVersionInspectionMode", "chapter-final"),
          writerMode,
          llmAccessToken: writerMode === "llm" ? llmAccessToken : "",
          author: document.querySelector("#author")?.value || "Policy Web",
          status: "작성중",
        })
      ),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "Full 버전 작성 요청에 실패했습니다.");
    }
    closeFullVersionModal();
    if (data.job) {
      activeJobId = data.job.id;
      openProgressModal(data.job);
      setMessage("간소화 문서를 기준으로 Full 버전 작성이 진행 중입니다.");
      startProgressPolling(activeJobId);
    }
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    if (fullVersionStartButton) fullVersionStartButton.disabled = false;
  }
}

function stageToActivity(stage) {
  return {
    stageLabel: stage.label,
    status: stage.status,
    attempt: stage.attempt,
    score: stage.score,
    threshold: stage.threshold,
    message: stage.message,
    artifact: stage.artifact,
    preview: stage.preview,
  };
}

function renderManualReview(job) {
  if (!manualReviewPanel) return;
  const review = job.manualReview;
  const waiting = job.status === "waiting_review" && review;
  if (progressManualReviewArea) progressManualReviewArea.hidden = !waiting;
  if (progressFocusCards) progressFocusCards.hidden = !!waiting;
  manualReviewPanel.hidden = !waiting;
  if (!waiting) {
    manualReviewPanel.classList.remove("revision-gate");
    if (manualReviewArtifact) manualReviewArtifact.innerHTML = "";
    setManualReviewBusy(false);
    return;
  }

  const isRevisionGate = review.reviewType === "revision_inspection_gate";
  manualReviewPanel.classList.toggle("revision-gate", isRevisionGate);
  const artifact = manualReviewHtmlArtifact(job, review);
  const stageLabel = review.stageLabel || "현재 챕터";
  manualReviewTitle.textContent = isRevisionGate ? "수정본 저장 여부 확인" : `${stageLabel} 수동 검수`;
  manualReviewMessage.textContent = isRevisionGate
    ? review.message || "수정본 점수와 남은 보완 필요 사항을 확인한 뒤 저장 여부를 선택해 주세요."
    : "중간 HTML을 확인한 뒤 그대로 이어서 작성하거나, 의견을 입력해 해당 챕터를 다시 작성할 수 있습니다.";
  if (manualReviewArtifact) {
    manualReviewArtifact.innerHTML = isRevisionGate
      ? manualReviewPreviewMarkup(review)
      : artifact?.url
      ? `
        <a class="manual-review-artifact-link" href="${escapeHtml(artifact.url)}" target="_blank" rel="noreferrer">
          <span>중간 산출물</span>
          <strong>${escapeHtml(progressDisplayText(artifact.name || `${stageLabel} HTML`))}</strong>
          <em>열기</em>
        </a>
      `
      : `
        <div class="manual-review-artifact-empty">
          아직 열 수 있는 HTML 스냅샷이 없습니다. 잠시 후 진행 상태를 새로 확인해 주세요.
        </div>
      `;
  }
  if (manualReviewInstructionField) manualReviewInstructionField.hidden = isRevisionGate;
  if (manualReviewInstructionLabel) manualReviewInstructionLabel.textContent = "다시 작성 의견";
  if (manualReviewInstruction) {
    manualReviewInstruction.placeholder = "예: 이 챕터의 정책 기준을 더 구체적인 값과 예외 조건 중심으로 다시 작성해줘.";
  }
  if (manualContinueButton) {
    manualContinueButton.textContent = isRevisionGate ? "점수 확인 후 저장" : "이어서 작성하기";
  }
  if (manualReviseButton) {
    manualReviseButton.textContent = isRevisionGate ? "저장하지 않고 중단" : "의견 반영해 다시 작성";
    manualReviseButton.dataset.action = isRevisionGate ? "stop" : "revise";
  }
  setManualReviewBusy(false);
}

function manualReviewPreviewMarkup(review) {
  const preview = review?.preview || {};
  const title = preview.title || "검수 결과";
  const items = Array.isArray(preview.items) ? preview.items.filter(Boolean) : [];
  const scoreLine = [
    Number.isFinite(Number(review?.score)) ? `점수 ${review.score}점` : "",
    Number.isFinite(Number(review?.threshold)) ? `기준 ${review.threshold}점` : "",
  ].filter(Boolean).join(" / ");
  const rows = [...(scoreLine ? [scoreLine] : []), ...items];
  return `
    <div class="manual-review-result-card">
      <strong>${escapeHtml(title)}</strong>
      <ul>
        ${rows.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>확인할 세부 결과가 없습니다.</li>"}
      </ul>
    </div>
  `;
}

function manualReviewHtmlArtifact(job, review) {
  if (review?.artifact && isHtmlArtifact(review.artifact)) {
    return review.artifact;
  }
  return collectProgressArtifacts(job, Array.isArray(job?.activity) ? job.activity : [])
    .filter((item) => isHtmlArtifact(item.artifact))
    .slice(-1)[0]?.artifact || null;
}

async function submitManualReview(action) {
  if (!activeJobId) return;
  if (!guardWritePermission("조회 권한은 수동 검수 응답을 실행할 수 없습니다.")) return;
  const instruction = manualReviewInstruction?.value.trim() || "";
  if (action === "revise" && !instruction) {
    setMessage("해당 챕터를 다시 작성하려면 반영할 의견을 입력해 주세요.", true);
    manualReviewInstruction?.focus();
    return;
  }

  setManualReviewBusy(true);
  try {
    const response = await fetch(apiPath(`/api/jobs/${encodeURIComponent(activeJobId)}/review`), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({ action, instruction })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "검수 응답을 전달하지 못했습니다.");
    }
    if (manualReviewInstruction) {
      manualReviewInstruction.value = "";
    }
    renderProgress(data.job);
    setMessage(
      action === "stop"
        ? "수정본 저장을 중단했습니다."
        : action === "revise"
        ? "보완 요청을 Agent에게 전달했습니다."
        : "다음 단계 진행을 요청했습니다."
    );
  } catch (error) {
    setMessage(error.message, true);
    setManualReviewBusy(false);
  }
}

function setManualReviewBusy(isBusy) {
  if (manualContinueButton) manualContinueButton.disabled = isBusy;
  if (manualReviseButton) manualReviseButton.disabled = isBusy;
  if (manualReviewInstruction) manualReviewInstruction.disabled = isBusy;
}

function statusLabel(status) {
  const labels = {
    queued: "대기",
    running: "진행 중",
    waiting_review: "검수 대기",
    review: "검수 대기",
    retry: "보완 중",
    canceling: "중단 중",
    canceled: "중단",
    done: "완료",
    completed: "완료",
    error: "오류",
    pending: "대기",
  };
  return labels[status] || status || "-";
}

function defaultStageMessage(status) {
  if (status === "pending") return "아직 시작 전입니다.";
  if (status === "done") return "완료되었습니다.";
  if (status === "review") return "사용자 검수를 기다리고 있습니다.";
  if (status === "retry") return "Inspector 보완 요청을 반영합니다.";
  if (status === "running") return "처리 중입니다.";
  return "";
}

function renderList() {
  if (!resultList) return;
  resultList.innerHTML = "";
  if (currentItems.length === 0) {
    resultList.innerHTML = '<div class="empty-state">아직 생성된 정책서가 없습니다. 위 작성 요청 영역에서 첫 정책서를 만들어보세요.</div>';
    return;
  }

  for (const item of currentItems) {
    const completed = isPolicyCompleted(item);
    const card = document.createElement("div");
    card.className = `result-card${item.name === selectedName ? " active" : ""}`;
    card.dataset.name = item.name;
    card.innerHTML = `
      <button class="result-card-main" type="button">
        <strong>${escapeHtml(item.topic)} 정책서</strong>
        <span>${escapeHtml(item.templateLabel)} · ${escapeHtml(item.version)} · ${escapeHtml(item.lifecycle?.label || "작성 중")}</span>
        <span>${formatDate(item.modified)} · ${formatSize(item.size)}</span>
      </button>
      ${completed || !canCurrentUserWritePolicies() ? "" : `<button class="delete-button" type="button" aria-label="${escapeHtml(item.name)} 삭제">삭제</button>`}
    `;
    card.querySelector(".result-card-main").addEventListener("click", () => selectPolicy(item.name));
    card.querySelector(".delete-button")?.addEventListener("click", () => deletePolicy(item.name));
    resultList.appendChild(card);
  }
}

async function deletePolicy(name) {
  if (!guardWritePermission("조회 권한은 문서 삭제를 실행할 수 없습니다.")) return;
  const item = currentItems.find((candidate) => candidate.name === name);
  if (!item) return;
  if (isPolicyCompleted(item)) {
    setMessage("작성 완료 상태에서는 '작성 완료 취소' 후에만 삭제할 수 있습니다.", true);
    return;
  }
  const deletedTopic = item.topic;
  const wasSelected = selectedName === name;

  const confirmed = window.confirm(
    `${item.name}을 삭제할까요?\n최종 HTML, 단계별 스냅샷, 검수 리포트가 함께 삭제됩니다.`
  );
  if (!confirmed) return;

  setMessage("정책서를 삭제하고 있습니다.");
  try {
    const response = await fetch(apiPath("/api/policies"), {
      method: "DELETE",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({ name })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "정책서 삭제에 실패했습니다.");
    }
    setMessage(`삭제 완료: ${data.deleted.name}`);
    await loadPolicies(wasSelected ? "" : selectedName, { autoSelect: false });
    if (wasSelected) {
      const remainingForTopic = latestItemForTopic(deletedTopic);
      if (remainingForTopic) {
        selectPolicy(remainingForTopic.name);
      } else {
        selectUnwrittenTopic(deletedTopic);
      }
    } else if (selectedName && currentItems.some((candidate) => candidate.name === selectedName)) {
      selectPolicy(selectedName);
    } else {
      clearPreview();
    }
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function togglePolicyCompletion() {
  if (!guardWritePermission("조회 권한은 작성 상태 변경을 실행할 수 없습니다.")) return;
  const item = selectedPolicyItem();
  if (!item) return;
  const completed = isPolicyCompleted(item);
  const nextStatus = completed ? "in_progress" : "completed";
  const nextLabel = completed ? "작성 중" : "작성 완료";
  const confirmMessage = completed
    ? `${item.name}의 작성 완료 상태를 취소할까요?\n취소 후에는 다시 편집, 삭제, Agent 수정 요청을 할 수 있습니다.`
    : `${item.name}을 작성 완료로 처리할까요?\n완료 상태에서는 '작성 완료 취소'만 가능합니다.`;
  if (!window.confirm(confirmMessage)) return;

  completionStatusButton.disabled = true;
  setMessage(`정책서 상태를 '${nextLabel}'로 변경하고 있습니다.`);
  try {
    const response = await fetch(apiPath("/api/policies/status"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({
        name: item.name,
        status: nextStatus,
        author: document.querySelector("#author")?.value || "Policy Web",
      })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "정책서 상태 변경에 실패했습니다.");
    }
    setMessage(`상태 변경 완료: ${data.item.documentStatus || nextLabel}`);
    await loadPolicies(data.item.name);
  } catch (error) {
    setMessage(error.message, true);
    completionStatusButton.disabled = false;
  }
}

async function deleteDraft(draft) {
  if (!draft) return;
  if (!guardWritePermission("조회 권한은 초안 삭제를 실행할 수 없습니다.")) return;
  const confirmed = window.confirm(
    `${draft.topic} 정책서 초안을 삭제할까요?\n보관된 중간 HTML, 체크포인트, 검수 리포트가 함께 삭제됩니다.`
  );
  if (!confirmed) return;

  const deletedTopic = draft.topic;
  setMessage("작성 중단 초안을 삭제하고 있습니다.");
  try {
    const response = await fetch(apiPath("/api/policies"), {
      method: "DELETE",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({ draftResumeFrom: draft.resumeFrom || draft.checkpoint?.path })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "초안 삭제에 실패했습니다.");
    }
    setMessage(`초안 삭제 완료: ${data.deleted.name}`);
    selectedDraft = null;
    await loadPolicies("", { autoSelect: false });
    const item = latestItemForTopic(deletedTopic);
    if (item) {
      selectPolicy(item.name);
    } else {
      selectUnwrittenTopic(deletedTopic);
    }
  } catch (error) {
    setMessage(error.message, true);
  }
}

function selectPolicy(name) {
  const item = currentItems.find((candidate) => candidate.name === name);
  if (!item) return;

  trackUserEvent("policy_selected", {
    name: item.name,
    topic: item.topic,
    templateLabel: item.templateLabel,
    lifecycle: item.lifecycle?.status || "",
  });
  selectedName = item.name;
  selectedAnalysisReferenceId = "";
  selectedTaskDefinitionId = "";
  selectedRequirementTopic = "";
  latestQaReviewReport = cachedQaReviewReport(item.name) || null;
  latestHealthCheckReport = cachedHealthCheckReport(item.name) || null;
  latestDevFormatExport = null;
  selectedDraft = null;
  clearVersionChangeView();
  loadEditorAssistState();
  hideSelectionRevisionButton();
  closeSelectionRevisionModal();
  exitEditMode(false);
  showDocumentWorkspace();
  showWorkspaceAssistLoading("문서를 읽고 AI 공동작업 정보를 정리하고 있습니다.");
  resetPreviewFrameHeight();
  clearPreviewInlineDocument();
  previewFrame.src = item.url;
  originalPreviewUrl = item.url;
  previewTitle.textContent = `${item.topic} 정책서`;
  previewMeta.textContent = [
    item.templateLabel,
    item.lifecycle?.label || "작성 중",
    item.specSync?.needed ? "Spec 보정 필요" : "",
    formatDate(item.modified),
    formatSize(item.size),
  ].filter(Boolean).join(" · ");
  renderPreviewTemplateState(item);
  renderWorkspaceTopicDirection(item.topic);
  openLink.href = item.url;
  setDownloadLink(item.url, item.name);
  setJsonDownloadLink(item.json?.url || "", item.json?.name || "");
  if (deleteSelectedButton) deleteSelectedButton.textContent = "삭제";
  renderVersionSelect(item);
  setPreviewActionMode("selected");
  configureRevisionPanelForPolicy(item);
  renderList();
  renderPolicyTopicList();
  focusWorkspaceOnCompact(resultArea);
}

function cacheDevQaReports(items) {
  (items || []).forEach((item) => {
    if (item?.name && item.devQaReview) {
      if (item.devQaReview.clientSessionId === CLIENT_SESSION_ID) {
        qaReviewReportsByPolicy.set(item.name, item.devQaReview);
      } else {
        sharedQaReviewReportsByPolicy.set(item.name, item.devQaReview);
      }
    }
  });
}

function cachedQaReviewReport(name = selectedName) {
  if (!name) return null;
  return qaReviewReportsByPolicy.get(name) || sharedQaReviewReportsByPolicy.get(name) || null;
}

function cacheHealthCheckReports(items) {
  (items || []).forEach((item) => {
    if (item?.name && item.healthCheck) {
      if (item.healthCheck.clientSessionId === CLIENT_SESSION_ID) {
        healthCheckReportsByPolicy.set(item.name, item.healthCheck);
      } else {
        sharedHealthCheckReportsByPolicy.set(item.name, item.healthCheck);
      }
    }
  });
}

function cachedHealthCheckReport(name = selectedName) {
  const key = name || healthCheckCacheKey();
  if (!key) return null;
  return healthCheckReportsByPolicy.get(key) || sharedHealthCheckReportsByPolicy.get(key) || null;
}

function healthCheckCacheKey() {
  if (selectedName) return selectedName;
  if (selectedDraft?.id) return `draft:${selectedDraft.id}`;
  return "";
}

function alignmentCheckCacheKey() {
  return selectedName || "";
}

function cachedAlignmentCheckReport(name = selectedName) {
  const key = name || alignmentCheckCacheKey();
  return key ? alignmentCheckReportsByPolicy.get(key) || null : null;
}

function selectDraft(draft) {
  if (!draft) return;

  selectedName = "";
  selectedAnalysisReferenceId = "";
  selectedTaskDefinitionId = "";
  selectedRequirementTopic = "";
  latestQaReviewReport = null;
  latestHealthCheckReport = null;
  latestDevFormatExport = null;
  selectedDraft = draft;
  clearVersionChangeView();
  loadEditorAssistState();
  hideSelectionRevisionButton();
  closeSelectionRevisionModal();
  exitEditMode(false);
  showDocumentWorkspace();
  showWorkspaceAssistLoading(draft.preview?.url ? "저장된 초안 내용을 읽고 있습니다." : "초안 미리보기 파일이 아직 없습니다.");
  setTopicSelectValue(draft.topic);
  updateRequestTopicSummary(getCurrentRequestTopic() || draft.topic);
  if (draft.preview?.url) {
    resetPreviewFrameHeight();
    clearPreviewInlineDocument();
    previewFrame.src = draft.preview.url;
    originalPreviewUrl = draft.preview.url;
    setDownloadLink(draft.preview.url, draft.preview.name || `${draft.topic || "policy"}_draft.html`);
    setJsonDownloadLink(draft.checkpoint?.url || "", draft.checkpoint?.name || "");
  } else {
    clearPreviewInlineDocument();
    previewFrame.removeAttribute("src");
    resetPreviewFrameHeight();
    originalPreviewUrl = "";
    setDownloadLink("", "");
    setJsonDownloadLink(draft.checkpoint?.url || "", draft.checkpoint?.name || "");
    renderWorkspaceAssistEmpty("저장된 미리보기 파일이 없어 이어서 작성 후 내용을 확인할 수 있습니다.");
  }
  previewTitle.textContent = `${draft.topic} 정책서`;
  previewMeta.textContent = [
    "작성 중단",
    draft.stageLabel ? `${draft.stageLabel}까지 저장` : "",
    draft.savedAt ? formatDate(draft.savedAt) : "",
  ]
    .filter(Boolean)
    .join(" · ");
  renderPreviewTemplateState(draft);
  renderWorkspaceTopicDirection(draft.topic);
  openLink.href = draft.preview?.url || draft.checkpoint?.url || "#";
  if (deleteSelectedButton) deleteSelectedButton.textContent = "초안 삭제";
  if (versionSelect) versionSelect.innerHTML = "";
  if (versionSelectWrap) versionSelectWrap.hidden = true;
  setPreviewActionMode("draft");
  configureRevisionPanelForDraft(draft);
  renderList();
  renderPolicyTopicList();
  setMessage("작성 중단된 초안을 불러왔습니다. '이어서 작성하기'로 다음 단계부터 진행할 수 있습니다.");
  focusWorkspaceOnCompact(resultArea);
}

function clearPreview(showRequest = true) {
  selectedName = "";
  selectedDraft = null;
  selectedAnalysisReferenceId = "";
  selectedTaskDefinitionId = "";
  selectedRequirementTopic = "";
  editorComments = [];
  editorSuggestions = [];
  selectedEditorContext = null;
  selectedEditorCommentId = "";
  clearEditorCommentHighlights();
  clearVersionChangeView();
  renderEditorAssistPanels();
  hideSelectionRevisionButton();
  closeSelectionRevisionModal();
  clearPreviewInlineDocument();
  previewFrame.removeAttribute("src");
  resetPreviewFrameHeight();
  hideWorkspaceAssistPanel();
  renderWorkspaceTopicDirection("");
  clearPreviewTemplateState();
  previewTitle.textContent = "미리보기";
  previewMeta.textContent = "생성된 파일을 선택하세요.";
  openLink.href = "#";
  setDownloadLink("", "");
  setJsonDownloadLink("", "");
  if (versionSelect) versionSelect.innerHTML = "";
  if (versionSelectWrap) versionSelectWrap.hidden = true;
  originalPreviewUrl = "";
  latestDevFormatExport = null;
  revisionPanel.hidden = true;
  exitEditMode(false);
  setPreviewActionMode("empty");
  if (showRequest) {
    showRequestWorkspace();
  }
  renderPolicyTopicList();
}

function showRequestWorkspace() {
  activeMainWorkspace = "request";
  if (welcomeArea) welcomeArea.hidden = true;
  if (channelPiArea) channelPiArea.hidden = true;
  if (requestArea) requestArea.hidden = false;
  if (resultArea) resultArea.hidden = true;
}

function showDocumentWorkspace() {
  activeMainWorkspace = "document";
  if (welcomeArea) welcomeArea.hidden = true;
  if (channelPiArea) channelPiArea.hidden = true;
  if (requestArea) requestArea.hidden = true;
  if (resultArea) resultArea.hidden = false;
}

function showWelcomeWorkspace() {
  activeMainWorkspace = "welcome";
  if (welcomeArea) welcomeArea.hidden = false;
  if (channelPiArea) channelPiArea.hidden = true;
  if (requestArea) requestArea.hidden = true;
  if (resultArea) resultArea.hidden = true;
}

function showChannelPiWorkspace() {
  if (channelPiArea) channelPiArea.hidden = false;
  channelPiHomeButton?.focus();
}

function closeChannelPiStatusModal() {
  if (channelPiArea) channelPiArea.hidden = true;
}

function goWelcomeHome() {
  hideSelectionRevisionButton();
  closeSelectionRevisionModal();
  clearPreviewSelection();
  clearEditorCommentHighlights();
  if (previewFrame?.contentDocument) {
    previewFrame.contentDocument.designMode = "off";
  }
  isEditing = false;
  previewFrame?.classList.remove("editing");
  selectedName = "";
  selectedDraft = null;
  selectedAnalysisReferenceId = "";
  selectedTaskDefinitionId = "";
  selectedRequirementTopic = "";
  originalPreviewUrl = "";
  latestDevFormatExport = null;
  clearVersionChangeView();
  if (topicSelect) {
    topicSelect.value = "";
    updateRequestTopicSummary("");
  }
  clearPreviewInlineDocument();
  closeWidePreviewModal();
  previewFrame?.removeAttribute("src");
  resetPreviewFrameHeight();
  hideWorkspaceAssistPanel();
  renderWorkspaceTopicDirection("");
  if (previewTitle) previewTitle.textContent = "미리보기";
  if (previewMeta) previewMeta.textContent = "생성된 파일을 선택하세요.";
  clearPreviewTemplateState();
  if (versionSelect) versionSelect.innerHTML = "";
  if (versionSelectWrap) versionSelectWrap.hidden = true;
  if (openLink) openLink.href = "#";
  setDownloadLink("", "");
  setJsonDownloadLink("", "");
  if (revisionPanel) revisionPanel.hidden = true;
  setPreviewActionMode("empty");
  showWelcomeWorkspace();
  renderPolicyTopicList();
  renderTopicChips(topicSearch?.value || "");
  setMessage("");
}

function renderVersionSelect(item) {
  if (!versionSelect || !versionSelectWrap || !item) return;
  const versions = policyVersionsForTopic(item.topic);
  versionSelect.innerHTML = versions
    .map((versionItem) => {
      const label = `${versionItem.version} · ${versionItem.templateLabel}`;
      return `<option value="${escapeHtml(versionItem.name)}">${escapeHtml(label)}</option>`;
    })
    .join("");
  versionSelect.value = item.name;
  versionSelectWrap.hidden = versions.length === 0;
  updateVersionChangeToggleState(item);
}

function policyVersionsForTopic(topic) {
  return currentItems
    .filter((item) => normalizeTopic(item.topic) === normalizeTopic(topic))
    .slice()
    .sort((a, b) => {
      const versionOrder = comparePolicyVersion(b.version, a.version);
      if (versionOrder !== 0) return versionOrder;
      return String(b.modified || "").localeCompare(String(a.modified || ""));
    });
}

function previousPolicyVersionItem(item = selectedPolicyItem()) {
  if (!item) return null;
  const currentVersion = item.version || "";
  const sameTopic = currentItems.filter(
    (candidate) => candidate.name !== item.name && normalizeTopic(candidate.topic) === normalizeTopic(item.topic)
  );
  const sameTemplate = sameTopic.filter((candidate) => {
    if (item.templateType && candidate.templateType) return candidate.templateType === item.templateType;
    return cleanWorkspaceText(candidate.templateLabel) === cleanWorkspaceText(item.templateLabel);
  });
  const candidates = (sameTemplate.length ? sameTemplate : sameTopic)
    .filter((candidate) => comparePolicyVersion(candidate.version, currentVersion) < 0)
    .sort((a, b) => {
      const versionOrder = comparePolicyVersion(b.version, a.version);
      if (versionOrder !== 0) return versionOrder;
      return String(b.modified || "").localeCompare(String(a.modified || ""));
    });
  return candidates[0] || null;
}

function updateVersionChangeToggleState(item = selectedPolicyItem()) {
  if (!versionChangeToggle) return;
  const previousItem = previousPolicyVersionItem(item);
  const canCompare = Boolean(item && previousItem && !selectedDraft && !isEditing);
  versionChangeToggle.hidden = !canCompare;
  versionChangeToggle.disabled = !canCompare || versionChangeLoading;
  versionChangeToggle.setAttribute("aria-pressed", String(versionChangeEnabled && canCompare));
  versionChangeToggle.textContent = versionChangeLoading
    ? "비교 중"
    : versionChangeEnabled && canCompare
      ? "표시 해제"
      : "변경 표시";
}

function clearVersionChangeView(options = {}) {
  const resetEnabled = options.resetEnabled !== false;
  versionChangeRequestId += 1;
  versionChangeLoading = false;
  if (resetEnabled) {
    versionChangeEnabled = false;
    versionChangeData = null;
  }
  if (versionChangeSummary) {
    versionChangeSummary.hidden = true;
    versionChangeSummary.innerHTML = "";
  }
  clearPreviewVersionChangeAnnotations();
  updateVersionChangeToggleState();
}

async function toggleVersionChangeView() {
  if (versionChangeLoading) return;
  if (versionChangeEnabled) {
    clearVersionChangeView();
    return;
  }
  await loadAndShowVersionChangeView();
}

async function loadAndShowVersionChangeView() {
  const item = selectedPolicyItem();
  const previousItem = previousPolicyVersionItem(item);
  if (!item || !previousItem) {
    setMessage("비교할 직전 버전이 없습니다.");
    updateVersionChangeToggleState(item);
    return;
  }

  const requestId = versionChangeRequestId + 1;
  versionChangeRequestId = requestId;
  versionChangeLoading = true;
  updateVersionChangeToggleState(item);
  renderVersionChangeSummaryLoading(item, previousItem);

  try {
    const [currentSpec, previousSpec] = await Promise.all([
      fetchPolicySpecJson(item),
      fetchPolicySpecJson(previousItem),
    ]);
    if (requestId !== versionChangeRequestId || selectedName !== item.name) return;
    const data = buildPolicyVersionChangeData(item, previousItem, currentSpec, previousSpec);
    versionChangeData = data;
    versionChangeEnabled = true;
    renderVersionChangeSummary(data);
    applyVersionChangeAnnotationsToPreview();
    const total = data.counts.added + data.counts.changed + data.counts.removed;
    setMessage(`${previousItem.version} 대비 변경 ${total}건을 본문에 표시했습니다.`);
  } catch (error) {
    if (requestId !== versionChangeRequestId) return;
    versionChangeEnabled = false;
    versionChangeData = null;
    renderVersionChangeSummaryError(error);
    setMessage(error.message || "버전 변경 비교에 실패했습니다.", true);
  } finally {
    if (requestId === versionChangeRequestId) {
      versionChangeLoading = false;
      updateVersionChangeToggleState(item);
    }
  }
}

function policySpecUrlForItem(item) {
  const explicitUrl = String(item?.json?.url || "").trim();
  if (explicitUrl) return explicitUrl;
  const htmlUrl = String(item?.url || "").trim();
  if (!htmlUrl) return "";
  try {
    const url = new URL(htmlUrl, window.location.origin);
    url.pathname = url.pathname.replace(/\.html?$/i, "_spec.json");
    url.search = "";
    return url.pathname + url.search;
  } catch (_error) {
    return htmlUrl.replace(/\.html?(?:\?.*)?$/i, "_spec.json");
  }
}

async function fetchPolicySpecJson(item) {
  const specUrl = policySpecUrlForItem(item);
  if (!specUrl) {
    throw new Error("비교할 JSON spec 경로를 찾지 못했습니다.");
  }
  const response = await fetch(specUrl, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${item?.version || "선택 버전"} JSON spec을 불러오지 못했습니다.`);
  }
  return response.json();
}

function buildPolicyVersionChangeData(currentItem, previousItem, currentSpec, previousSpec) {
  const changes = [];
  const counts = { added: 0, changed: 0, removed: 0 };
  const byCollection = [];

  VERSION_CHANGE_COLLECTIONS.forEach((definition) => {
    const currentRecords = versionChangeRecordsForCollection(currentSpec, definition);
    const previousRecords = versionChangeRecordsForCollection(previousSpec, definition);
    const collectionCounts = { added: 0, changed: 0, removed: 0 };
    const keys = new Set([...currentRecords.keys(), ...previousRecords.keys()]);
    keys.forEach((key) => {
      const currentRecord = currentRecords.get(key);
      const previousRecord = previousRecords.get(key);
      if (currentRecord && !previousRecord) {
        collectionCounts.added += 1;
        changes.push(buildVersionChangeItem("added", definition, currentRecord, previousRecord));
      } else if (!currentRecord && previousRecord) {
        collectionCounts.removed += 1;
        changes.push(buildVersionChangeItem("removed", definition, currentRecord, previousRecord));
      } else if (currentRecord && previousRecord && currentRecord.signature !== previousRecord.signature) {
        collectionCounts.changed += 1;
        changes.push(buildVersionChangeItem("changed", definition, currentRecord, previousRecord));
      }
    });
    counts.added += collectionCounts.added;
    counts.changed += collectionCounts.changed;
    counts.removed += collectionCounts.removed;
    if (collectionCounts.added || collectionCounts.changed || collectionCounts.removed) {
      byCollection.push({ label: definition.label, ...collectionCounts });
    }
  });

  changes.forEach((change, index) => {
    change.index = index;
  });
  changes.sort((a, b) => {
    const typeOrder = { added: 0, changed: 1, removed: 2 };
    const typeDiff = (typeOrder[a.type] ?? 9) - (typeOrder[b.type] ?? 9);
    if (typeDiff !== 0) return typeDiff;
    return String(a.collectionLabel).localeCompare(String(b.collectionLabel), "ko") ||
      String(a.title).localeCompare(String(b.title), "ko");
  });
  changes.forEach((change, index) => {
    change.index = index;
  });

  return {
    currentItem,
    previousItem,
    counts,
    byCollection,
    changes,
  };
}

function versionChangeRecordsForCollection(spec, definition) {
  const rows = Array.isArray(spec?.[definition.key]) ? spec[definition.key] : [];
  const records = new Map();
  rows.forEach((row, rowIndex) => {
    const record = buildVersionChangeRecord(row, rowIndex, definition);
    if (!record.key) return;
    records.set(record.key, record);
  });
  return records;
}

function buildVersionChangeRecord(row, rowIndex, definition) {
  const raw = row && typeof row === "object" ? row : { value: row };
  const id = cleanWorkspaceText(firstVersionChangeValue(raw, definition.idKeys));
  const fallbackId = definition.fallback === "transition"
    ? cleanWorkspaceText([
        raw.current_state || raw.from,
        raw.event,
        raw.next_state || raw.to,
      ].filter(Boolean).join(" -> "))
    : "";
  const key = id || fallbackId || `${definition.key}:${rowIndex}`;
  const title = cleanWorkspaceText(firstVersionChangeValue(raw, definition.titleKeys)) ||
    cleanWorkspaceText(raw.title || raw.label || raw.description || raw.content || key);
  const searchTexts = uniqueCompactValues([
    id,
    raw.id,
    raw.policy_id,
    raw.usecase_id,
    raw.requirement_id,
    raw.detail_id,
    title,
    raw.name,
    raw.detail_name,
    raw.description,
    raw.content,
    raw.criteria,
    raw.rationale,
    Array.isArray(raw.details) ? raw.details.join(" ") : "",
    Array.isArray(raw.items) ? raw.items.map((item) => `${item?.id || ""} ${item?.name || ""}`).join(" ") : "",
  ]);
  return {
    key,
    id,
    title,
    raw,
    searchTexts,
    signature: stableVersionChangeSignature(raw),
  };
}

function firstVersionChangeValue(raw, keys = []) {
  for (const key of keys) {
    const value = raw?.[key];
    if (value !== undefined && value !== null && cleanWorkspaceText(value)) return value;
  }
  return "";
}

function buildVersionChangeItem(type, definition, currentRecord, previousRecord) {
  const record = currentRecord || previousRecord;
  return {
    type,
    collectionKey: definition.key,
    collectionLabel: definition.label,
    id: record?.id || "",
    title: record?.title || record?.key || "",
    current: currentRecord || null,
    previous: previousRecord || null,
    changedFields: currentRecord && previousRecord
      ? changedVersionChangeFields(currentRecord.raw, previousRecord.raw)
      : [],
  };
}

function changedVersionChangeFields(currentRaw, previousRaw) {
  const keys = new Set([...Object.keys(currentRaw || {}), ...Object.keys(previousRaw || {})]);
  const labels = {
    name: "명칭",
    description: "설명",
    content: "정책 내용",
    details: "세부 구성",
    items: "정책 항목",
    related_functions: "관련 기능",
    related_policies: "관련 정책",
    process_ids: "관련 프로세스",
    mapped_to: "매핑",
    rationale: "반영 근거",
    criteria: "전이 기준",
  };
  return [...keys]
    .filter((key) => !versionChangeIgnoredKey(key))
    .filter((key) => stableVersionChangeSignature(currentRaw?.[key]) !== stableVersionChangeSignature(previousRaw?.[key]))
    .map((key) => labels[key] || key)
    .slice(0, 4);
}

function stableVersionChangeSignature(value) {
  return JSON.stringify(stableVersionChangeValue(value));
}

function stableVersionChangeValue(value) {
  if (Array.isArray(value)) {
    const normalizedItems = value.map((item) => stableVersionChangeValue(item));
    if (normalizedItems.every((item) => item === null || ["string", "number", "boolean"].includes(typeof item))) {
      return normalizedItems.slice().sort((a, b) => String(a).localeCompare(String(b), "ko"));
    }
    return normalizedItems;
  }
  if (!value || typeof value !== "object") {
    return typeof value === "string" ? cleanWorkspaceText(value) : value;
  }
  return Object.keys(value)
    .filter((key) => !versionChangeIgnoredKey(key))
    .sort()
    .reduce((acc, key) => {
      acc[key] = stableVersionChangeValue(value[key]);
      return acc;
    }, {});
}

function versionChangeIgnoredKey(key) {
  return [
    "created_at",
    "updated_at",
    "modified",
    "generated_at",
    "source_file",
    "html_file",
    "output_file",
    "version",
  ].includes(String(key || "").toLowerCase());
}

function uniqueCompactValues(values = []) {
  const seen = new Set();
  const result = [];
  values.forEach((value) => {
    const text = cleanWorkspaceText(value);
    if (!text || seen.has(text)) return;
    seen.add(text);
    result.push(text);
  });
  return result;
}

function renderVersionChangeSummaryLoading(item, previousItem) {
  if (!versionChangeSummary) return;
  versionChangeSummary.hidden = false;
  versionChangeSummary.innerHTML = `
    <div class="version-change-summary-head">
      <div>
        <span class="version-change-eyebrow">버전 변경</span>
        <strong>직전 버전과 비교하고 있습니다</strong>
        <p>${escapeHtml(previousItem.version || "이전 버전")} → ${escapeHtml(item.version || "현재 버전")}</p>
      </div>
      <span class="version-change-loading-dot" aria-hidden="true"></span>
    </div>
  `;
}

function renderVersionChangeSummaryError(error) {
  if (!versionChangeSummary) return;
  versionChangeSummary.hidden = false;
  versionChangeSummary.innerHTML = `
    <div class="version-change-summary-head">
      <div>
        <span class="version-change-eyebrow">버전 변경</span>
        <strong>변경 비교 실패</strong>
        <p>${escapeHtml(error?.message || "비교 정보를 만들지 못했습니다.")}</p>
      </div>
    </div>
  `;
}

function renderVersionChangeSummary(data) {
  if (!versionChangeSummary) return;
  const total = data.counts.added + data.counts.changed + data.counts.removed;
  const visibleChanges = data.changes.slice(0, 36);
  const moreCount = Math.max(0, data.changes.length - visibleChanges.length);
  const collectionHtml = data.byCollection.slice(0, 8).map((item) => `
    <span>${escapeHtml(item.label)} ${item.added + item.changed + item.removed}</span>
  `).join("");
  const listHtml = visibleChanges.length
    ? visibleChanges.map((change) => `
        <button class="version-change-item ${escapeHtml(change.type)}" type="button" data-version-change-index="${change.index}">
          <span class="version-change-type">${escapeHtml(versionChangeTypeLabel(change.type))}</span>
          <strong>${escapeHtml(versionChangeItemTitle(change))}</strong>
          <em>${escapeHtml(versionChangeItemMeta(change))}</em>
        </button>
      `).join("")
    : '<div class="version-change-empty">직전 버전 대비 구조화 항목 변경이 없습니다.</div>';
  versionChangeSummary.hidden = false;
  versionChangeSummary.innerHTML = `
    <div class="version-change-summary-head">
      <div>
        <span class="version-change-eyebrow">버전 변경</span>
        <strong>${escapeHtml(data.previousItem.version || "이전 버전")} 대비 본문 변경 표시</strong>
        <p>추가 ${data.counts.added}건 · 수정 ${data.counts.changed}건 · 삭제 ${data.counts.removed}건</p>
      </div>
      <div class="version-change-counts" aria-label="변경 유형별 건수">
        <span class="added">추가 ${data.counts.added}</span>
        <span class="changed">수정 ${data.counts.changed}</span>
        <span class="removed">삭제 ${data.counts.removed}</span>
      </div>
    </div>
    ${collectionHtml ? `<div class="version-change-collections">${collectionHtml}</div>` : ""}
    <div class="version-change-list">${listHtml}</div>
    ${moreCount ? `<p class="version-change-more">외 ${moreCount}건은 요약만 집계했습니다.</p>` : ""}
    ${total ? '<p class="version-change-help">목록을 누르면 본문에서 찾은 위치로 이동합니다. 삭제된 항목은 현재 본문에 위치가 없을 수 있습니다.</p>' : ""}
  `;
}

function versionChangeTypeLabel(type) {
  if (type === "added") return "추가";
  if (type === "changed") return "수정";
  if (type === "removed") return "삭제";
  return "변경";
}

function versionChangeItemTitle(change) {
  const id = cleanWorkspaceText(change.id);
  const title = cleanWorkspaceText(change.title);
  if (id && title && id !== title) return `${id} · ${title}`;
  return title || id || "변경 항목";
}

function versionChangeItemMeta(change) {
  const fields = change.changedFields?.length ? ` · ${change.changedFields.join(", ")}` : "";
  return `${change.collectionLabel}${fields}`;
}

function clearPreviewVersionChangeAnnotations(doc = null) {
  let targetDoc = doc;
  if (!targetDoc) {
    try {
      targetDoc = previewFrame?.contentDocument;
    } catch (_error) {
      return;
    }
  }
  if (!targetDoc?.body) return;
  targetDoc.querySelectorAll(`[data-nc-version-change-badge], .${VERSION_CHANGE_BADGE_CLASS}`).forEach((element) => {
    element.remove();
  });
  targetDoc.querySelectorAll(`.${VERSION_CHANGE_HIGHLIGHT_CLASS}, .${VERSION_CHANGE_ACTIVE_CLASS}, .nc-preview-version-change-badge-host`).forEach((element) => {
    element.classList.remove(
      VERSION_CHANGE_HIGHLIGHT_CLASS,
      VERSION_CHANGE_ACTIVE_CLASS,
      "nc-preview-version-change-added",
      "nc-preview-version-change-changed",
      "nc-preview-version-change-removed",
      "nc-preview-version-change-badge-host"
    );
    element.removeAttribute("data-nc-version-change-index");
    element.removeAttribute("data-nc-version-change-type");
  });
}

function applyVersionChangeAnnotationsToPreview() {
  if (!versionChangeEnabled || !versionChangeData) return;
  let doc;
  try {
    doc = previewFrame?.contentDocument;
  } catch (_error) {
    return;
  }
  if (!doc?.body) return;
  clearPreviewVersionChangeAnnotations(doc);
  versionChangeData.changes.forEach((change) => {
    if (change.type === "removed") return;
    const target = findVersionChangeTargetElement(doc, change);
    if (!target) return;
    decorateVersionChangeTarget(doc, target, change);
  });
}

function findVersionChangeTargetElement(doc, change) {
  const record = change.current || change.previous;
  const searchTexts = uniqueCompactValues([
    change.id,
    record?.id,
    record?.title,
    ...(record?.searchTexts || []),
  ]).filter((text) => text.length >= 2);
  const candidates = versionChangeTargetCandidates(doc);
  for (const text of searchTexts) {
    const match = findVersionChangeTargetByText(candidates, text);
    if (match) return match;
  }
  return null;
}

function versionChangeTargetCandidates(doc) {
  if (!doc?.body) return [];
  const candidates = [];
  const seen = new Set();
  doc.body.querySelectorAll("tr, li, p, h1, h2, h3, h4, h5, td, th, .box, .plain-text, section, article").forEach((element) => {
    if (!element || seen.has(element)) return;
    seen.add(element);
    candidates.push(element);
  });
  return candidates;
}

function findVersionChangeTargetByText(candidates, text) {
  const normalizedNeedle = cleanWorkspaceText(text);
  const compactNeedle = compactVersionChangeText(normalizedNeedle);
  if (!normalizedNeedle && !compactNeedle) return null;
  const exactMatch = candidates.find((candidate) => {
    const candidateText = cleanWorkspaceText(candidate.textContent || "");
    return candidateText.includes(normalizedNeedle);
  });
  if (exactMatch) return preferredVersionChangeElement(exactMatch);
  if (compactNeedle.length < 4) return null;
  const compactMatch = candidates.find((candidate) =>
    compactVersionChangeText(candidate.textContent || "").includes(compactNeedle)
  );
  return compactMatch ? preferredVersionChangeElement(compactMatch) : null;
}

function preferredVersionChangeElement(element) {
  if (!element) return null;
  if (["TD", "TH"].includes(element.tagName)) {
    const row = element.closest("tr");
    if (row && cleanWorkspaceText(row.textContent || "").length <= 1800) return row;
  }
  if (element.tagName === "SECTION" || element.tagName === "ARTICLE") {
    const row = element.querySelector("tr");
    if (row) return row;
  }
  return element;
}

function compactVersionChangeText(value) {
  return String(value || "").replace(/\s+/g, "").toLowerCase();
}

function decorateVersionChangeTarget(doc, target, change) {
  const host = versionChangeBadgeHost(target);
  if (!host) return;
  target.classList.add(
    VERSION_CHANGE_HIGHLIGHT_CLASS,
    `nc-preview-version-change-${change.type}`
  );
  target.setAttribute("data-nc-version-change-index", String(change.index));
  target.setAttribute("data-nc-version-change-type", change.type);
  host.classList.add("nc-preview-version-change-badge-host");
  host.setAttribute("data-nc-version-change-index", String(change.index));
  host.setAttribute("data-nc-version-change-type", change.type);
  const badge = doc.createElement("button");
  badge.type = "button";
  badge.className = `${VERSION_CHANGE_BADGE_CLASS} nc-preview-version-change-${change.type}`;
  badge.setAttribute("data-nc-version-change-badge", "true");
  badge.setAttribute("data-version-change-index", String(change.index));
  badge.title = `${versionChangeTypeLabel(change.type)}: ${versionChangeItemTitle(change)}`;
  badge.textContent = versionChangeTypeLabel(change.type);
  badge.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    focusVersionChangeItem(change.index);
  });
  host.appendChild(badge);
}

function versionChangeBadgeHost(target) {
  if (!target) return null;
  if (target.tagName === "TR") {
    return [...target.children].reverse().find((cell) => ["TD", "TH"].includes(cell.tagName)) || target;
  }
  return target;
}

function focusVersionChangeItem(index) {
  if (!versionChangeEnabled || !versionChangeData || Number.isNaN(index)) return false;
  applyVersionChangeAnnotationsToPreview();
  const change = versionChangeData.changes.find((item) => item.index === index);
  let doc;
  try {
    doc = previewFrame?.contentDocument;
  } catch (_error) {
    return false;
  }
  if (!doc?.body || !change) return false;
  doc.querySelectorAll(`.${VERSION_CHANGE_ACTIVE_CLASS}`).forEach((element) => {
    element.classList.remove(VERSION_CHANGE_ACTIVE_CLASS);
  });
  const safeIndex = String(Math.trunc(Number(index)));
  const target = doc.querySelector(`[data-nc-version-change-index="${safeIndex}"]`);
  if (!target) {
    setMessage(`${versionChangeItemTitle(change)} 항목은 현재 본문에서 위치를 찾지 못했습니다.`);
    return false;
  }
  const block = target.closest?.(`.${VERSION_CHANGE_HIGHLIGHT_CLASS}`) || target;
  block.classList.add(VERSION_CHANGE_ACTIVE_CLASS);
  try {
    block.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
    previewFrame?.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
  } catch (_error) {
    block.scrollIntoView();
  }
  setMessage(`${versionChangeTypeLabel(change.type)} 항목으로 이동했습니다: ${versionChangeItemTitle(change)}`);
  return true;
}

function enterEditMode() {
  const editingAnalysisReference = hasAnalysisReferenceSelection();
  if ((!selectedName && !editingAnalysisReference) || !previewFrame.contentDocument) return;
  if (!guardWritePermission("조회 권한은 직접 편집을 실행할 수 없습니다.")) return;
  if (selectedName && selectedPolicyCompleted()) {
    setMessage("작성 완료 상태에서는 '작성 완료 취소' 후에만 직접 편집할 수 있습니다.", true);
    return;
  }
  hideSelectionRevisionButton();
  closeSelectionRevisionModal();
  clearVersionChangeView();
  editingBaseHash = selectedPolicyItem()?.contentHash || "";
  editingOriginalHtml = previewDocumentHtmlForSave(previewFrame.contentDocument);
  editingOriginalText = cleanWorkspaceText(previewFrame.contentDocument.body?.innerText || previewFrame.contentDocument.body?.textContent || "");
  isEditing = true;
  closeWidePreviewModal();
  document.body.classList.add("direct-editing");
  previewFrame.contentDocument.designMode = "on";
  previewFrame.contentWindow?.focus();
  previewFrame.classList.add("editing");
  if (editorModeChip) editorModeChip.hidden = false;
  if (workspaceAssistEnabled) {
    setWorkspaceAssistEnabled(false, { persist: false });
  } else {
    hideWorkspaceAssistPanel();
  }
  setPreviewActionMode("editing");
  updateEditorToolbarState();
  revisionPanel.hidden = true;
  setMessage(
    editingAnalysisReference
      ? "현황 분석 직접 편집 모드입니다. 본문을 수정한 뒤 저장하면 바로 반영됩니다."
      : "직접 편집 모드입니다. 본문을 수정한 뒤 '저장 검토'에서 저장 전 검증을 확인해 주세요."
  );
}

function exitEditMode(reloadOriginal = true) {
  hideSelectionRevisionButton();
  closeSelectionRevisionModal();
  closeDiagramEditor();
  if (previewFrame.contentDocument) {
    previewFrame.contentDocument.designMode = "off";
  }
  isEditing = false;
  editingBaseHash = "";
  editingOriginalHtml = "";
  editingOriginalText = "";
  document.body.classList.remove("direct-editing");
  previewFrame.classList.remove("editing");
  previewFrame.hidden = false;
  closeWidePreviewModal();
  if (editorModeChip) editorModeChip.hidden = true;
  setPreviewActionMode(selectedName ? "selected" : hasAnalysisReferenceSelection() ? "analysis-reference" : "empty");
  updateEditorToolbarState();
  if (selectedDraft) {
    configureRevisionPanelForDraft(selectedDraft);
  } else {
    revisionPanel.hidden = !selectedName || selectedPolicyCompleted();
  }
  if (reloadOriginal && originalPreviewUrl) {
    previewFrame.src = originalPreviewUrl;
  }
}

function runEditorCommand(command) {
  if (!isEditing || !command || !previewFrame?.contentDocument) return;
  const doc = previewFrame.contentDocument;
  const win = previewFrame.contentWindow;
  try {
    win?.focus();
    if (["insertTableRowAbove", "insertTableRowBelow", "deleteTableRow"].includes(command)) {
      if (!runTableRowCommand(command)) {
        updateEditorToolbarState();
      }
      return;
    }
    if (command === "insertLineBreak") {
      if (!doc.execCommand("insertLineBreak")) {
        doc.execCommand("insertHTML", false, "<br/>");
      }
      updateEditorToolbarState();
      return;
    }
    if (command === "highlight") {
      if (!doc.execCommand("hiliteColor", false, "#fff59d")) {
        doc.execCommand("backColor", false, "#fff59d");
      }
      updateEditorToolbarState();
      return;
    }
    if (command === "indent" || command === "outdent") {
      applyEditorIndent(command === "indent" ? 1 : -1);
      updateEditorToolbarState();
      return;
    }
    doc.execCommand(command, false, null);
    updateEditorToolbarState();
  } catch (_error) {
    setMessage("편집 도구 실행 중 오류가 발생했습니다.", true);
  }
}

function applyEditorFontSize(value) {
  if (!isEditing || !previewFrame?.contentDocument) return;
  const size = Number.parseInt(String(value || ""), 10);
  if (![13, 14, 15, 16, 21, 31].includes(size)) return;
  const doc = previewFrame.contentDocument;
  const selection = doc.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
    setMessage("폰트 크기를 적용할 텍스트를 먼저 드래그해서 선택해 주세요.", true);
    previewFrame.contentWindow?.focus();
    return;
  }
  const range = selection.getRangeAt(0);
  const blockTargets = editorFontSizeBlockTargets(doc, range);
  if (blockTargets.length) {
    blockTargets.forEach((target) => {
      target.style.fontSize = `${size}px`;
      target.setAttribute("data-nc-font-size", `${size}`);
    });
    setMessage(`선택한 문서 블록 ${blockTargets.length}개에 폰트 크기 ${size}px을 적용했습니다.`);
    updateEditorToolbarState();
    return;
  }
  const span = doc.createElement("span");
  span.style.fontSize = `${size}px`;
  span.setAttribute("data-nc-font-size", `${size}`);
  try {
    span.appendChild(range.extractContents());
    range.insertNode(span);
    selection.removeAllRanges();
    const nextRange = doc.createRange();
    nextRange.selectNodeContents(span);
    selection.addRange(nextRange);
    setMessage(`선택 영역에 문서 폰트 크기 ${size}px을 적용했습니다.`);
  } catch (_error) {
    setMessage("선택한 영역에 폰트 크기를 적용하지 못했습니다.", true);
  }
  updateEditorToolbarState();
}

function editorFontSizeBlockTargets(doc, range) {
  const selector = [
    "p",
    "li",
    "td",
    "th",
    "h1",
    "h2",
    "h3",
    "h4",
    ".plain-text",
    ".principle-text",
    ".policy-item-title",
    ".policy-item-content",
    ".policy-item-line",
  ].join(",");
  const targets = [...(doc.body?.querySelectorAll(selector) || [])].filter((element) => {
    try {
      return range.intersectsNode(element) && cleanWorkspaceText(element.textContent || "");
    } catch (_error) {
      return false;
    }
  });
  return targets.filter((element) => !targets.some((candidate) => candidate !== element && element.contains(candidate)));
}

const EDITOR_INDENT_STEP = 24;
const EDITOR_INDENT_MAX = 144;

function applyEditorIndent(direction) {
  if (!isEditing || !previewFrame?.contentDocument) return;
  const doc = previewFrame.contentDocument;
  const selection = doc.getSelection();
  if (!selection || selection.rangeCount === 0) {
    setMessage("들여쓰기할 문서 영역을 먼저 선택해 주세요.", true);
    previewFrame.contentWindow?.focus();
    return;
  }
  const range = selection.getRangeAt(0);
  const targets = editorIndentBlockTargets(doc, range, selection);
  if (!targets.length) {
    const browserCommand = direction > 0 ? "indent" : "outdent";
    if (doc.execCommand(browserCommand, false, null)) {
      setMessage(direction > 0 ? "선택 영역을 들여쓰기했습니다." : "선택 영역을 내어쓰기했습니다.");
    } else {
      setMessage("선택한 영역에 들여쓰기 서식을 적용하지 못했습니다.", true);
    }
    return;
  }
  let changedCount = 0;
  targets.forEach((target) => {
    const current = editorIndentValue(target);
    const next = Math.max(0, Math.min(EDITOR_INDENT_MAX, current + direction * EDITOR_INDENT_STEP));
    if (next === current) return;
    setEditorIndentValue(target, next);
    changedCount += 1;
  });
  const actionLabel = direction > 0 ? "들여쓰기" : "내어쓰기";
  if (changedCount) {
    setMessage(`선택한 문서 블록 ${changedCount}개를 ${actionLabel}했습니다.`);
  } else {
    setMessage(direction > 0 ? "더 이상 들여쓰기할 수 없습니다." : "더 이상 내어쓰기할 여백이 없습니다.");
  }
}

function editorIndentBlockTargets(doc, range, selection) {
  const selector = editorIndentBlockSelector();
  if (selection?.isCollapsed) {
    const current = elementFromSelectionNode(selection.anchorNode)?.closest(selector);
    return current ? [current] : [];
  }
  const targets = [...(doc.body?.querySelectorAll(selector) || [])].filter((element) => {
    try {
      return range.intersectsNode(element) && cleanWorkspaceText(element.textContent || "");
    } catch (_error) {
      return false;
    }
  });
  return targets.filter((element) => !targets.some((candidate) => candidate !== element && element.contains(candidate)));
}

function editorIndentBlockSelector() {
  return [
    "p",
    "li",
    "td",
    "th",
    "h1",
    "h2",
    "h3",
    "h4",
    ".plain-text",
    ".principle-text",
    ".policy-item-title",
    ".policy-item-content",
    ".policy-item-line",
  ].join(",");
}

function editorIndentValue(element) {
  const dataValue = parseEditorIndentPx(element.getAttribute("data-nc-indent"));
  if (Number.isFinite(dataValue)) return dataValue;
  const styleValue = element.matches("td, th") ? element.style.paddingLeft : element.style.marginLeft;
  const parsed = parseEditorIndentPx(styleValue);
  return Number.isFinite(parsed) ? parsed : 0;
}

function parseEditorIndentPx(value) {
  const raw = String(value || "").trim();
  if (!raw) return Number.NaN;
  if (/^-?\d+(\.\d+)?$/.test(raw)) return Number.parseFloat(raw);
  const match = raw.match(/^(-?\d+(?:\.\d+)?)px$/i);
  return match ? Number.parseFloat(match[1]) : Number.NaN;
}

function setEditorIndentValue(element, value) {
  const indent = Math.max(0, Math.min(EDITOR_INDENT_MAX, Number(value) || 0));
  const isTableCell = element.matches("td, th");
  if (!indent) {
    if (isTableCell) {
      element.style.paddingLeft = "";
    } else {
      element.style.marginLeft = "";
      if (element.classList.contains("policy-item-line")) element.style.display = "";
    }
    element.removeAttribute("data-nc-indent");
    return;
  }
  if (isTableCell) {
    element.style.paddingLeft = `${indent}px`;
  } else {
    element.style.marginLeft = `${indent}px`;
    if (element.classList.contains("policy-item-line")) element.style.display = "block";
  }
  element.setAttribute("data-nc-indent", `${indent}`);
}

function applyEditorBulletStyle(value) {
  if (!isEditing || !previewFrame?.contentDocument) return;
  if (value === "unordered") {
    runEditorCommand("insertUnorderedList");
    return;
  }
  if (value === "ordered") {
    runEditorCommand("insertOrderedList");
    return;
  }
  if (value === "policy-title" || value === "policy-line") {
    insertPolicyBulletMarkup(value);
  }
}

function insertPolicyBulletMarkup(type) {
  const doc = previewFrame?.contentDocument;
  if (!doc) return;
  const selection = doc.getSelection();
  const selectedText = selection?.toString() || "";
  const lines = selectedText
    .split(/\n+/)
    .map((line) => cleanWorkspaceText(line).replace(/^[•\-]\s*/, ""))
    .filter(Boolean);
  const fallback = type === "policy-title" ? "정책 항목명" : "정책 내용을 입력하세요.";
  const sourceLines = lines.length ? lines : [fallback];
  const html = sourceLines.map((line) => {
    const text = escapeHtml(line);
    if (type === "policy-title") {
      return `<div class="policy-item-title">• ${text}</div>`;
    }
    return `<span class="policy-item-line">- ${text}<br/></span>`;
  }).join("");
  try {
    previewFrame.contentWindow?.focus();
    if (!doc.execCommand("insertHTML", false, html)) {
      const range = selection && selection.rangeCount ? selection.getRangeAt(0) : null;
      if (!range) throw new Error("missing range");
      const wrapper = doc.createElement("span");
      wrapper.innerHTML = html;
      range.deleteContents();
      range.insertNode(wrapper);
    }
    setMessage(type === "policy-title" ? "정책 항목 불릿을 삽입했습니다." : "정책 문장 불릿을 삽입했습니다.");
  } catch (_error) {
    setMessage("문서 불릿을 삽입하지 못했습니다.", true);
  }
  updateEditorToolbarState();
}

function runTableRowCommand(command) {
  const context = getEditableTableRowContext();
  if (!context) {
    setMessage("표 본문 셀 안에서 행을 선택한 뒤 다시 시도해 주세요.", true);
    return false;
  }
  if (context.blockedReason) {
    setMessage(context.blockedReason, true);
    return false;
  }
  const { doc, tbody, row, rows } = context;
  if (command === "deleteTableRow" && rows.length <= 1) {
    setMessage("마지막 본문 행은 삭제할 수 없습니다. 필요한 경우 내용만 비워 주세요.", true);
    return false;
  }
  if (command === "insertTableRowAbove" || command === "insertTableRowBelow") {
    const newRow = createEditableTableRowClone(doc, row);
    if (command === "insertTableRowAbove") {
      tbody.insertBefore(newRow, row);
    } else {
      tbody.insertBefore(newRow, row.nextSibling);
    }
    placeCaretInFirstEditableCell(newRow);
    setMessage("표 본문 행을 추가했습니다.");
    return true;
  }
  if (command === "deleteTableRow") {
    const focusRow = row.previousElementSibling || row.nextElementSibling || null;
    row.remove();
    if (focusRow) {
      placeCaretInFirstEditableCell(focusRow);
    }
    setMessage("선택한 표 본문 행을 삭제했습니다.");
    return true;
  }
  return false;
}

function getEditableTableRowContext() {
  if (!isEditing || !previewFrame?.contentDocument) return null;
  let doc;
  let selection;
  try {
    doc = previewFrame.contentDocument;
    selection = doc.getSelection();
  } catch (_error) {
    return null;
  }
  const anchorNode = selection?.anchorNode || null;
  const cell = elementFromSelectionNode(anchorNode)?.closest("td, th");
  const row = cell?.closest("tr");
  const table = row?.closest("table");
  const tbody = row?.parentElement?.tagName === "TBODY" ? row.parentElement : row?.closest("tbody");
  if (!doc || !cell || !row || !table) return null;
  const rows = tbody ? [...tbody.children].filter((candidate) => candidate.tagName === "TR") : [];
  if (cell.tagName === "TH" || row.closest("thead") || row.querySelector("th")) {
    return {
      doc,
      table,
      tbody,
      row,
      rows,
      blockedReason: "컬럼 헤더와 타이틀 행은 보호되어 있어 본문 행만 추가/삭제할 수 있습니다.",
    };
  }
  if (!tbody) {
    return {
      doc,
      table,
      tbody: null,
      row,
      rows: [],
      blockedReason: "본문 영역이 없는 표는 행 구조를 직접 변경할 수 없습니다.",
    };
  }
  return { doc, table, tbody, row, rows, tableInfo: detectEditorTableInfo(table), blockedReason: "" };
}

function createEditableTableRowClone(doc, row) {
  const newRow = row.cloneNode(true);
  [...newRow.querySelectorAll("td, th")].forEach((cell) => {
    cell.innerHTML = "<br/>";
  });
  const tableInfo = detectEditorTableInfo(row.closest("table"));
  applySmartRowDefaults(newRow, row.closest("tbody") || row.parentElement, tableInfo);
  return newRow;
}

function placeCaretInFirstEditableCell(row) {
  if (!row || !previewFrame?.contentWindow) return;
  const cell = row.querySelector("td, th");
  if (!cell) return;
  const doc = previewFrame.contentDocument;
  const win = previewFrame.contentWindow;
  const range = doc.createRange();
  range.selectNodeContents(cell);
  range.collapse(true);
  const selection = win.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  win.focus();
}

function tableHeaders(table) {
  if (!table) return [];
  const headerCells = table.querySelectorAll("thead th");
  const fallbackCells = headerCells.length ? headerCells : table.querySelectorAll("tr:first-child th, tr:first-child td");
  return [...fallbackCells].map((cell) => cleanWorkspaceText(cell.textContent));
}

function detectEditorTableInfo(table) {
  const headers = tableHeaders(table);
  const signature = headers.join("|");
  const info = { type: "일반 표", key: "generic", headers, requiredHeaders: [] };
  if (signature.includes("상태 코드|상태명|정의|대표 후속 처리")) {
    return { ...info, type: "상태 코드표", key: "state", requiredHeaders: ["상태 코드", "상태명"] };
  }
  if (signature.includes("현재 상태|전이 이벤트|다음 상태|처리 기준 및 후속 처리")) {
    return { ...info, type: "상태 전이표", key: "transition", requiredHeaders: ["현재 상태", "전이 이벤트", "다음 상태"] };
  }
  if (signature.includes("프로세스 ID|프로세스명|설명|관련 기능|관련 정책")) {
    return { ...info, type: "프로세스표", key: "process", requiredHeaders: ["프로세스 ID", "프로세스명", "관련 기능", "관련 정책"] };
  }
  if (signature.includes("기능 ID|기능명|설명|세부 기능 구성")) {
    return { ...info, type: "기능표", key: "function", requiredHeaders: ["기능 ID", "기능명"] };
  }
  if (signature.includes("정책 ID|정책명|설명|정책 항목")) {
    return { ...info, type: "정책표", key: "policy", requiredHeaders: ["정책 ID", "정책명"] };
  }
  if (signature.includes("유즈케이스 ID|액터|유즈케이스명|설명|프로세스 정의 대상")) {
    return { ...info, type: "유즈케이스표", key: "usecase", requiredHeaders: ["유즈케이스 ID", "액터", "유즈케이스명"] };
  }
  return info;
}

function applySmartRowDefaults(newRow, rowGroup, tableInfo) {
  if (!newRow || !rowGroup || !tableInfo || tableInfo.key === "generic" || tableInfo.key === "transition") return;
  const firstCell = newRow.querySelector("td, th");
  if (!firstCell) return;
  const existingIds = [...rowGroup.querySelectorAll("tr")]
    .map((row) => cleanWorkspaceText(row.querySelector("td, th")?.textContent || ""))
    .filter(Boolean);
  const nextId = nextPolicyElementId(existingIds, tableInfo.key);
  if (nextId) firstCell.textContent = nextId;
}

function nextPolicyElementId(existingIds, key) {
  const prefixByKey = {
    usecase: "UC",
    state: "ST",
    process: "PR",
    function: "FN",
    policy: "PG",
  };
  const prefix = prefixByKey[key];
  if (!prefix) return "";
  let maxValue = 0;
  let width = 2;
  existingIds.forEach((id) => {
    const match = String(id).match(new RegExp(`^${prefix}[-_ ]?(\\d+)$`, "i"));
    if (!match) return;
    maxValue = Math.max(maxValue, Number(match[1] || 0));
    width = Math.max(width, match[1].length);
  });
  return `${prefix}-${String(maxValue + 1).padStart(width, "0")}`;
}

function updateEditorToolbarState() {
  const editingEnabled = isEditing && (!selectedName || !selectedPolicyCompleted());
  editorToolButtons.forEach((button) => {
    button.disabled = !editingEnabled;
  });
  if (editorFontSizeSelect) editorFontSizeSelect.disabled = !editingEnabled;
  if (editorBulletStyleSelect) editorBulletStyleSelect.disabled = !editingEnabled;
  if (!editingEnabled) return;
  const context = getEditableTableRowContext();
  const tableActionEnabled = Boolean(context && !context.blockedReason);
  editorTableActionButtons.forEach((button) => {
    button.disabled = !tableActionEnabled;
  });
}

function setDiagramEditorTab(tabName) {
  const normalized = ["usecase", "state", "process"].includes(tabName) ? tabName : "usecase";
  diagramEditorTabs.forEach((tab) => {
    const active = tab.dataset.diagramTab === normalized;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  diagramEditorPanes.forEach((pane) => {
    pane.classList.toggle("active", pane.dataset.diagramPane === normalized);
  });
}

async function openDiagramEditor() {
  if (!selectedName || selectedDraft) {
    setMessage("다이어그램을 편집할 정책서를 먼저 선택해 주세요.", true);
    return;
  }
  if (!isEditing) {
    setMessage("직접 편집 모드에서 다이어그램을 편집할 수 있습니다.", true);
    return;
  }
  setDiagramEditorStatus("다이어그램 데이터를 불러오고 있습니다.");
  if (diagramEditorModal) diagramEditorModal.hidden = false;
  setDiagramEditorTab("usecase");
  setDiagramEditorLoading(true);
  try {
    const response = await fetch(apiPath(`/api/policies/diagram-data?name=${encodeURIComponent(selectedName)}`));
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "다이어그램 데이터를 불러오지 못했습니다.");
    }
    fillDiagramEditor(data.diagram || {});
    diagramEditorBaseHash = selectedPolicyItem()?.contentHash || editingBaseHash || "";
    if (diagramEditorSummary) {
      const diagram = data.diagram || {};
      diagramEditorSummary.textContent = `${diagram.name || selectedName} · 액터 ${(diagram.actors || []).length}개 · 유즈케이스 ${(diagram.usecases || []).length}개 · 상태 ${(diagram.states || []).length}개 · 프로세스 ${(diagram.processes || []).length}개`;
    }
    setDiagramEditorStatus("수정 후 저장하면 HTML, JSON spec, BPMN 파일과 viewer를 함께 재생성합니다.");
  } catch (error) {
    setDiagramEditorStatus(error.message || "다이어그램 데이터를 불러오는 중 오류가 발생했습니다.", true);
  } finally {
    setDiagramEditorLoading(false);
  }
}

function closeDiagramEditor() {
  if (diagramEditorModal) diagramEditorModal.hidden = true;
  diagramEditorBaseHash = "";
}

function fillDiagramEditor(diagram) {
  setJsonTextarea(diagramActorsInput, diagram.actors || []);
  setJsonTextarea(diagramUsecasesInput, diagram.usecases || []);
  setJsonTextarea(diagramStatesInput, diagram.states || []);
  setJsonTextarea(diagramTransitionsInput, diagram.stateTransitions || []);
  setJsonTextarea(diagramProcessesInput, diagram.processes || []);
  if (diagramEditorSaveMode) diagramEditorSaveMode.value = "new_version";
}

function setJsonTextarea(target, value) {
  if (!target) return;
  target.value = JSON.stringify(value || [], null, 2);
}

function readDiagramEditorPayload() {
  return {
    actors: parseDiagramJsonInput(diagramActorsInput, "액터 JSON"),
    usecases: parseDiagramJsonInput(diagramUsecasesInput, "유즈케이스 JSON"),
    states: parseDiagramJsonInput(diagramStatesInput, "상태 코드 JSON"),
    stateTransitions: parseDiagramJsonInput(diagramTransitionsInput, "상태 전이 JSON"),
    processes: parseDiagramJsonInput(diagramProcessesInput, "프로세스 JSON"),
  };
}

function parseDiagramJsonInput(input, label) {
  const raw = String(input?.value || "").trim();
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      throw new Error("array-required");
    }
    return parsed;
  } catch (_error) {
    throw new Error(`${label} 형식이 올바르지 않습니다. JSON 배열로 입력해 주세요.`);
  }
}

async function saveDiagramEditor() {
  if (!selectedName) return;
  let diagram;
  try {
    diagram = readDiagramEditorPayload();
  } catch (error) {
    setDiagramEditorStatus(error.message, true);
    return;
  }
  setDiagramEditorLoading(true);
  setDiagramEditorStatus("다이어그램 수정본을 저장하고 산출물을 재생성하고 있습니다.");
  try {
    const response = await fetch(apiPath("/api/policies/diagram-edit"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({
        name: selectedName,
        diagram,
        saveMode: diagramEditorSaveMode?.value || "new_version",
        author: document.querySelector("#author")?.value || "Policy Web",
        baseHash: diagramEditorBaseHash || editingBaseHash,
      })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "다이어그램 저장에 실패했습니다.");
    }
    closeDiagramEditor();
    exitEditMode(false);
    setMessage(`다이어그램 저장 완료: ${data.item.name}`);
    await loadPolicies(data.item.name);
  } catch (error) {
    setDiagramEditorStatus(error.message || "다이어그램 저장 중 오류가 발생했습니다.", true);
  } finally {
    setDiagramEditorLoading(false);
  }
}

function setDiagramEditorLoading(loading) {
  if (diagramEditorModal) diagramEditorModal.dataset.busy = loading ? "true" : "false";
  if (diagramEditorSaveButton) diagramEditorSaveButton.disabled = loading;
  diagramEditorTabs.forEach((tab) => {
    tab.disabled = loading;
  });
}

function setDiagramEditorStatus(text, isError = false) {
  if (!diagramEditorStatus) return;
  diagramEditorStatus.textContent = text || "";
  diagramEditorStatus.classList.toggle("error", Boolean(isError));
}

function configureRevisionPanelForPolicy(item) {
  if (!revisionPanel) return;
  revisionPanel.hidden = isPolicyCompleted(item);
  if (revisionRequest) {
    revisionRequest.placeholder = "예: 정책 상세에서 예외 처리 기준을 더 구체화해줘.";
  }
  if (revisionButton) {
    revisionButton.textContent = "수정 Agent 실행";
    revisionButton.disabled = false;
  }
}

function configureRevisionPanelForDraft(draft) {
  if (!revisionPanel) return;
  revisionPanel.hidden = !draft;
  if (revisionRequest) {
    revisionRequest.placeholder = "예: 현재까지 작성된 초안에서 상태 전이와 프로세스 연결을 보완한 뒤 이어서 작성해줘.";
  }
  if (revisionButton) {
    revisionButton.textContent = "보완 요청 반영 후 이어서 작성";
    revisionButton.disabled = !draft;
  }
}

function renderPreviewTemplateState(item) {
  const templateType = item?.templateType === "full" ? "full" : item?.templateType === "simple" ? "simple" : "";
  const label = item?.templateLabel || (templateType === "full" ? "Full" : templateType === "simple" ? "간소화" : "");
  if (previewTemplateBadge) {
    previewTemplateBadge.hidden = !templateType;
    previewTemplateBadge.textContent = label || "";
    previewTemplateBadge.classList.toggle("simple", templateType === "simple");
  }
  if (previewTemplateHint) {
    const showSimpleHint = templateType === "simple" && isPolicyCompleted(item);
    previewTemplateHint.hidden = !showSimpleHint;
    previewTemplateHint.textContent = showSimpleHint ? "Full 버전 작성 후 AI Input Export를 사용할 수 있습니다." : "";
  }
}

function clearPreviewTemplateState() {
  if (previewTemplateBadge) {
    previewTemplateBadge.hidden = true;
    previewTemplateBadge.textContent = "";
    previewTemplateBadge.classList.remove("simple");
  }
  if (previewTemplateHint) {
    previewTemplateHint.hidden = true;
    previewTemplateHint.textContent = "";
  }
}

function setPreviewActionMode(mode) {
  const editing = mode === "editing";
  const draft = mode === "draft";
  const policySelected = mode === "selected" || (editing && Boolean(selectedName));
  const analysisReferenceSelected = mode === "analysis-reference" || (editing && hasAnalysisReferenceSelection());
  const selected = policySelected || analysisReferenceSelected;
  const completed = policySelected && selectedPolicyCompleted();
  const writeAllowed = canCurrentUserWritePolicies();
  const adminActionAllowed = canCurrentUserRunAdminPolicyActions();
  const canOpenWidePreview = selected && !draft && !editing;
  const selectedItem = selectedPolicyItem();
  const canRunDevFormatExport = policySelected && !draft && !editing && selectedItem?.templateType === "full";

  resultArea?.classList.toggle("analysis-reference-mode", analysisReferenceSelected);

  if (resumeDraftButton) {
    resumeDraftButton.hidden = !draft || !writeAllowed;
    resumeDraftButton.disabled = !draft || !writeAllowed;
  }
  if (rewritePolicyButton) {
    rewritePolicyButton.hidden = !policySelected || editing || completed || !writeAllowed || !adminActionAllowed;
    rewritePolicyButton.disabled = !policySelected || editing || completed || !writeAllowed || !adminActionAllowed || Boolean(progressTimer);
  }
  if (fullVersionButton) {
    const canCreateFullVersion = writeAllowed && adminActionAllowed && policySelected && !editing && canCreateFullVersionFromSelectedPolicy();
    fullVersionButton.hidden = !canCreateFullVersion;
    fullVersionButton.disabled = !canCreateFullVersion || Boolean(progressTimer);
  }
  if (devFormatExportButton) {
    devFormatExportButton.hidden = !canRunDevFormatExport;
    devFormatExportButton.disabled = !canRunDevFormatExport || devFormatExportInFlight;
  }
  if (deleteSelectedButton) {
    deleteSelectedButton.hidden = (!policySelected && !draft) || editing || completed || !writeAllowed;
    deleteSelectedButton.disabled = (!policySelected && !draft) || editing || completed || !writeAllowed;
  }
  if (completionStatusButton) {
    completionStatusButton.hidden = !policySelected || editing || !writeAllowed;
    completionStatusButton.disabled = !policySelected || editing || !writeAllowed;
    completionStatusButton.textContent = completed ? "작성 완료 취소" : "작성 완료";
    completionStatusButton.classList.toggle("complete-cancel", completed);
  }
  if (widePreviewButton) {
    widePreviewButton.hidden = !canOpenWidePreview;
    widePreviewButton.disabled = !canOpenWidePreview;
  }
  if (downloadLink) {
    const hasDownloadTarget = Boolean(downloadLink.getAttribute("href")) && downloadLink.getAttribute("href") !== "#";
    downloadLink.hidden = (!selected && !draft) || !hasDownloadTarget;
    downloadLink.setAttribute("aria-disabled", String(downloadLink.hidden));
  }
  if (jsonDownloadLink) {
    const hasJsonTarget = Boolean(jsonDownloadLink.getAttribute("href")) && jsonDownloadLink.getAttribute("href") !== "#";
    jsonDownloadLink.hidden = (!selected && !draft) || !hasJsonTarget;
    jsonDownloadLink.setAttribute("aria-disabled", String(jsonDownloadLink.hidden));
  }
  if (uploadHtmlButton) {
    uploadHtmlButton.hidden = editing || !policySelected || draft || completed || !writeAllowed;
    uploadHtmlButton.disabled = editing || !policySelected || draft || completed || !writeAllowed;
  }
  if (uploadJsonButton) {
    uploadJsonButton.hidden = editing || !policySelected || draft || completed || !writeAllowed;
    uploadJsonButton.disabled = editing || !policySelected || draft || completed || !writeAllowed;
  }
  editButton.hidden = !selected || editing || completed || !writeAllowed;
  editButton.disabled = !selected || editing || completed || !writeAllowed;
  if (saveEditButton) {
    saveEditButton.textContent = analysisReferenceSelected ? "저장" : "저장 검토";
  }
  saveEditButton.hidden = !editing || completed || !writeAllowed;
  cancelEditButton.hidden = !editing || completed || !writeAllowed;
  saveEditButton.disabled = completed || !writeAllowed;
  cancelEditButton.disabled = completed || !writeAllowed;
  if (editorModeChip) editorModeChip.hidden = !editing;
  if (editorToolbar) editorToolbar.hidden = !editing || completed || !writeAllowed;
  editorToolButtons.forEach((button) => {
    button.disabled = !editing || completed || !writeAllowed;
  });
  if (editorFontSizeSelect) {
    editorFontSizeSelect.disabled = !editing || completed || !writeAllowed;
    editorFontSizeSelect.value = "";
  }
  if (editorBulletStyleSelect) {
    editorBulletStyleSelect.disabled = !editing || completed || !writeAllowed;
    editorBulletStyleSelect.value = "";
  }
  updateVersionChangeToggleState(policySelected && !editing ? selectedPolicyItem() : null);
  // 새 창 열기는 문서 확인용 보조 액션이라 기본 버튼 흐름에서는 숨긴다.
  openLink.hidden = true;
  if (editing) {
    closeWidePreviewModal();
  }
  updatePolicyWorkspaceActionVisibility();
  updateEditorCommentComposer();
  updatePreviewMoreActionsVisibility();
}

function isTaskDefinitionWorkspaceView() {
  return Boolean((selectedAnalysisReferenceId || selectedTaskDefinitionId || selectedRequirementTopic) && !selectedName && !selectedDraft);
}

function updatePolicyWorkspaceActionVisibility() {
  const hidePolicyActions = isTaskDefinitionWorkspaceView();
  if (workspaceTitleActions) {
    workspaceTitleActions.hidden = hidePolicyActions;
    workspaceTitleActions.setAttribute("aria-hidden", String(hidePolicyActions));
  }
  policyWorkspaceActionButtons.forEach((button) => {
    button.hidden = hidePolicyActions;
    button.setAttribute("aria-hidden", String(hidePolicyActions));
  });
  if (devFormatExportButton && hidePolicyActions) {
    devFormatExportButton.hidden = true;
    devFormatExportButton.setAttribute("aria-hidden", "true");
  } else if (devFormatExportButton) {
    devFormatExportButton.setAttribute("aria-hidden", String(devFormatExportButton.hidden));
  }
}

function updatePreviewMoreActionsVisibility() {
  if (!previewMoreActions) return;
  const secondaryActions = [
    downloadLink,
    jsonDownloadLink,
    uploadHtmlButton,
    uploadJsonButton,
    deleteSelectedButton,
    openLink,
  ].filter(Boolean);
  const hasVisibleAction = secondaryActions.some((item) => !item.hidden);
  previewMoreActions.hidden = !hasVisibleAction;
  if (!hasVisibleAction) previewMoreActions.open = false;
}

function setDownloadLink(url, fileName) {
  if (!downloadLink) return;
  const cleanUrl = String(url || "").trim();
  const cleanName = String(fileName || "").trim();
  if (!cleanUrl) {
    downloadLink.href = "#";
    downloadLink.removeAttribute("download");
    return;
  }
  downloadLink.href = cleanUrl;
  downloadLink.setAttribute("download", cleanName || "policy.html");
}

function setJsonDownloadLink(url, fileName) {
  if (!jsonDownloadLink) return;
  const cleanUrl = String(url || "").trim();
  const cleanName = String(fileName || "").trim();
  if (!cleanUrl) {
    jsonDownloadLink.href = "#";
    jsonDownloadLink.removeAttribute("download");
    return;
  }
  jsonDownloadLink.href = cleanUrl;
  jsonDownloadLink.setAttribute("download", cleanName || "policy.json");
}

async function uploadHtmlFile(file) {
  if (!guardWritePermission("조회 권한은 HTML 업로드를 실행할 수 없습니다.")) {
    resetHtmlUploadInput();
    return;
  }
  if (!selectedName || selectedDraft) {
    setMessage("HTML을 등록할 기준 문서를 먼저 선택해 주세요.", true);
    resetHtmlUploadInput();
    return;
  }
  if (selectedPolicyCompleted()) {
    setMessage("작성 완료 상태에서는 '작성 완료 취소' 후에만 HTML을 등록할 수 있습니다.", true);
    resetHtmlUploadInput();
    return;
  }
  const fileName = String(file?.name || "").trim();
  if (!fileName || !/\.html?$/i.test(fileName)) {
    setMessage("HTML 파일(.html 또는 .htm)만 업로드할 수 있습니다.", true);
    resetHtmlUploadInput();
    return;
  }
  if (file.size > HTML_UPLOAD_MAX_BYTES) {
    setMessage("HTML 파일은 10MB 이하만 업로드할 수 있습니다.", true);
    resetHtmlUploadInput();
    return;
  }

  if (uploadHtmlButton) uploadHtmlButton.disabled = true;
  setMessage("선택한 문서 기준으로 HTML 파일을 새 버전으로 등록하고 있습니다.");
  try {
    const html = await file.text();
    const response = await fetch(apiPath("/api/policies/upload"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({
        baseName: selectedName,
        name: fileName,
        html,
        author: document.querySelector("#author")?.value || "Policy Web",
      })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "HTML 파일 등록에 실패했습니다.");
    }
    setMessage(`HTML 등록 완료: ${data.item.name}`);
    await loadPolicies(data.item.name);
  } catch (error) {
    setMessage(error.message || "HTML 파일 등록 중 오류가 발생했습니다.", true);
  } finally {
    if (uploadHtmlButton) uploadHtmlButton.disabled = false;
    resetHtmlUploadInput();
  }
}

function resetHtmlUploadInput() {
  if (uploadHtmlInput) uploadHtmlInput.value = "";
}

async function uploadJsonFile(file) {
  if (!guardWritePermission("조회 권한은 JSON 업로드를 실행할 수 없습니다.")) {
    resetJsonUploadInput();
    return;
  }
  if (!selectedName || selectedDraft) {
    setMessage("JSON을 등록할 기준 문서를 먼저 선택해 주세요.", true);
    resetJsonUploadInput();
    return;
  }
  if (selectedPolicyCompleted()) {
    setMessage("작성 완료 상태에서는 '작성 완료 취소' 후에만 JSON을 등록할 수 있습니다.", true);
    resetJsonUploadInput();
    return;
  }
  const fileName = String(file?.name || "").trim();
  if (!fileName || !/\.json$/i.test(fileName)) {
    setMessage("JSON 파일(.json)만 업로드할 수 있습니다.", true);
    resetJsonUploadInput();
    return;
  }
  if (file.size > JSON_UPLOAD_MAX_BYTES) {
    setMessage("JSON 파일은 10MB 이하만 업로드할 수 있습니다.", true);
    resetJsonUploadInput();
    return;
  }

  if (uploadJsonButton) uploadJsonButton.disabled = true;
  setMessage("선택한 문서 기준으로 JSON 파일을 렌더링해 새 버전으로 등록하고 있습니다.");
  try {
    const json = await file.text();
    const response = await fetch(apiPath("/api/policies/upload-json"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({
        baseName: selectedName,
        name: fileName,
        json,
        author: document.querySelector("#author")?.value || "Policy Web",
      })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "JSON 파일 등록에 실패했습니다.");
    }
    const warnings = Array.isArray(data.warnings) ? data.warnings : [];
    const warningSuffix = warnings.length ? ` 검증 경고 ${warnings.length}건은 JSON 메타에 기록했습니다.` : "";
    setMessage(`JSON 등록 완료: ${data.item.name}${warningSuffix}`);
    await loadPolicies(data.item.name);
  } catch (error) {
    setMessage(error.message || "JSON 파일 등록 중 오류가 발생했습니다.", true);
  } finally {
    if (uploadJsonButton) uploadJsonButton.disabled = false;
    resetJsonUploadInput();
  }
}

function resetJsonUploadInput() {
  if (uploadJsonInput) uploadJsonInput.value = "";
}

async function saveEditedPolicy() {
  if (!selectedName && hasAnalysisReferenceSelection()) {
    await saveEditedAnalysisReference();
    return;
  }
  if (!selectedName || !previewFrame.contentDocument) return;
  if (!guardWritePermission("조회 권한은 문서 저장을 실행할 수 없습니다.")) return;
  if (selectedPolicyCompleted()) {
    setMessage("작성 완료 상태에서는 '작성 완료 취소' 후에만 수정할 수 있습니다.", true);
    return;
  }
  saveEditButton.disabled = true;
  const editedHtml = previewDocumentHtmlForSave(previewFrame.contentDocument);
  const editReview = buildEditReview(previewFrame.contentDocument, editedHtml);
  const saveMode = await promptEditSaveMode(editReview);
  if (!saveMode) {
    saveEditButton.disabled = false;
    setMessage("편집 저장이 취소되었습니다.");
    return;
  }
  if (saveMode === "overwrite" && editReview.blockingCount > 0) {
    saveEditButton.disabled = false;
    setMessage("Critical 검증 이슈가 있어 기존 버전 덮어쓰기는 제한됩니다. 새 버전으로 저장해 주세요.", true);
    return;
  }
  setMessage(
    saveMode === "overwrite"
      ? "수정본을 현재 버전에 반영하고 있습니다."
      : "수정본을 새 버전으로 저장하고 있습니다."
  );
  try {
    const response = await fetch(apiPath("/api/policies/edit"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({
        name: selectedName,
        html: editedHtml,
        author: document.querySelector("#author")?.value || "Policy Web",
        saveMode,
        baseHash: editingBaseHash,
      })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "수정본 저장에 실패했습니다.");
    }
    exitEditMode(false);
    setMessage(
      saveMode === "overwrite"
        ? `기존 버전 수정 완료: ${data.item.name}`
        : `새 버전 저장 완료: ${data.item.name}`
    );
    await loadPolicies(data.item.name);
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    saveEditButton.disabled = false;
  }
}

async function saveEditedAnalysisReference() {
  const reference = selectedAnalysisReference();
  if (!reference?.url || !previewFrame.contentDocument) return;
  if (!guardWritePermission("조회 권한은 현황 분석 문서 저장을 실행할 수 없습니다.")) return;
  saveEditButton.disabled = true;
  const editedHtml = previewDocumentHtmlForSave(previewFrame.contentDocument);
  setMessage("현황 분석 수정본을 저장하고 있습니다.");
  try {
    const response = await fetch(apiPath("/api/reference-html/edit"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({
        id: reference.id,
        url: reference.url,
        html: editedHtml,
        author: document.querySelector("#author")?.value || "Policy Web",
        baseHash: editingBaseHash,
      })),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "현황 분석 수정본 저장에 실패했습니다.");
    }
    const nextUrl = cacheBustedReferenceUrl(reference.url);
    exitEditMode(false);
    previewFrame.src = nextUrl;
    originalPreviewUrl = nextUrl;
    openLink.href = nextUrl;
    setDownloadLink(nextUrl, data.item?.name || analysisReferenceFileName(reference));
    setMessage(`현황 분석 수정 완료: ${reference.title}`);
  } catch (error) {
    setMessage(error.message || "현황 분석 수정본 저장 중 오류가 발생했습니다.", true);
  } finally {
    saveEditButton.disabled = false;
  }
}

function previewDocumentHtmlForSave(doc) {
  const clone = doc.documentElement.cloneNode(true);
  clone.querySelectorAll("[data-nc-preview-style], .nc-preview-diagram-static").forEach((node) => {
    node.remove();
  });
  clone.querySelectorAll(`[data-nc-preview-comment-marker], .${PREVIEW_COMMENT_MARKER_CLASS}`).forEach((node) => {
    node.remove();
  });
  clone.querySelectorAll(`.${PREVIEW_COMMENT_HIGHLIGHT_CLASS}, .${PREVIEW_COMMENT_ANCHOR_CLASS}`).forEach((node) => {
    node.classList.remove(
      PREVIEW_COMMENT_HIGHLIGHT_CLASS,
      PREVIEW_COMMENT_ANCHOR_CLASS,
      "nc-preview-comment-open",
      "nc-preview-comment-hold",
      "nc-preview-comment-resolved",
      "nc-preview-comment-open-anchor",
      "nc-preview-comment-hold-anchor"
    );
    node.removeAttribute("data-nc-comment-count");
    node.removeAttribute("data-nc-comment-title");
    node.removeAttribute("data-nc-comment-latest");
    node.removeAttribute("data-nc-comment-marker-for");
  });
  return `<!DOCTYPE html>\n${clone.outerHTML}`;
}

function injectWidePreviewStyle(html) {
  const isAnalysisReferencePreview = hasAnalysisReferenceSelection();
  const previewPageRule = isAnalysisReferencePreview
    ? `
    .page {
      width: calc(100% - 24px) !important;
      max-width: none !important;
      margin: 0 auto !important;
      padding: 20px 0 144px !important;
      box-sizing: border-box !important;
    }
    @media (max-width: 720px) {
      .page {
        width: calc(100% - 20px) !important;
        padding: 14px 0 112px !important;
      }
    }
    `
    : `
    .page {
      width: min(1820px, calc(100% - 36px)) !important;
      max-width: calc(100% - 36px) !important;
      margin: clamp(10px, 1.5vw, 22px) auto clamp(24px, 3vw, 44px) !important;
      padding-left: clamp(16px, 2.4vw, 42px) !important;
      padding-right: clamp(16px, 2.4vw, 42px) !important;
      box-sizing: border-box !important;
      box-shadow: 0 26px 64px rgba(20, 28, 45, 0.12);
    }
    @media (max-width: 900px) {
      .page {
        width: calc(100% - 14px) !important;
        max-width: calc(100% - 14px) !important;
        margin: 8px auto 18px !important;
        padding-left: 12px !important;
        padding-right: 12px !important;
      }
    }
    `;
  const styleBlock = `
<style data-nc-wide-preview-style>
  html, body {
    min-height: 100%;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    scrollbar-width: thin;
    scrollbar-color: rgba(120, 138, 161, 0.7) rgba(232, 238, 245, 0.95);
  }
  body {
    background:
      radial-gradient(circle at top right, rgba(49, 130, 246, 0.08), transparent 26%),
      linear-gradient(180deg, #f3f6fa 0%, #edf2f7 100%) !important;
  }
  body::-webkit-scrollbar {
    width: 14px;
  }
  body::-webkit-scrollbar-track {
    background: rgba(232, 238, 245, 0.95);
  }
  body::-webkit-scrollbar-thumb {
    border: 3px solid rgba(232, 238, 245, 0.95);
    border-radius: 999px;
    background: rgba(120, 138, 161, 0.72);
  }
  ${previewPageRule}
  table {
    width: 100% !important;
    max-width: 100% !important;
  }
</style>`;
  if (/<\/head>/i.test(html)) {
    return html.replace(/<\/head>/i, `${styleBlock}\n</head>`);
  }
  return `${styleBlock}\n${html}`;
}

function buildWidePreviewDocument(doc) {
  return injectWidePreviewStyle(previewDocumentHtmlForSave(doc));
}

function applyWidePreviewResponsiveLayout(doc) {
  if (!doc || doc.__ncWidePreviewResponsiveLayout) return;
  const style = doc.createElement("style");
  style.setAttribute("data-nc-wide-preview-runtime", "true");
  style.textContent = `
    html, body {
      min-height: 100%;
      max-width: 100%;
      overflow-y: auto !important;
      overflow-x: hidden !important;
    }
    body {
      margin: 0 !important;
      background:
        radial-gradient(circle at top right, rgba(49, 130, 246, 0.08), transparent 26%),
        linear-gradient(180deg, #f3f6fa 0%, #edf2f7 100%) !important;
    }
    .page {
      width: min(1820px, calc(100% - 36px)) !important;
      max-width: calc(100% - 36px) !important;
      margin: clamp(10px, 1.5vw, 22px) auto clamp(24px, 3vw, 44px) !important;
      padding-left: clamp(16px, 2.4vw, 42px) !important;
      padding-right: clamp(16px, 2.4vw, 42px) !important;
      box-sizing: border-box !important;
      box-shadow: 0 26px 64px rgba(20, 28, 45, 0.12);
    }
    @media (max-width: 900px) {
      .page {
        width: calc(100% - 14px) !important;
        max-width: calc(100% - 14px) !important;
        margin: 8px auto 18px !important;
        padding-left: 12px !important;
        padding-right: 12px !important;
      }
    }
    table,
    img,
    svg,
    canvas,
    video,
    pre {
      max-width: 100% !important;
    }
    table {
      width: 100% !important;
    }
  `;
  (doc.head || doc.documentElement).appendChild(style);
  doc.__ncWidePreviewResponsiveLayout = true;
}

function syncWidePreviewFromCurrentFrame() {
  if (!widePreviewFrame || !previewFrame?.contentDocument) return;
  const sourceUrl = String(previewFrame.getAttribute("src") || previewFrame.src || "").trim();
  const sandboxValue = previewFrame.getAttribute("sandbox");
  if (sandboxValue) {
    widePreviewFrame.setAttribute("sandbox", sandboxValue);
  }
  if (sourceUrl && !sourceUrl.startsWith("about:blank")) {
    widePreviewFrame.removeAttribute("srcdoc");
    widePreviewFrame.src = sourceUrl;
  } else {
    widePreviewFrame.removeAttribute("src");
    widePreviewFrame.srcdoc = buildWidePreviewDocument(previewFrame.contentDocument);
    try {
      widePreviewFrame.contentWindow?.scrollTo(0, 0);
    } catch (_error) {
      // srcdoc reload will usually reset scroll automatically.
    }
  }
  if (widePreviewSummary) {
    const title = previewTitle?.textContent?.trim() || "정책서";
    const meta = previewMeta?.textContent?.trim() || "본문을 넓은 팝업에서 읽기 전용으로 확인합니다.";
    widePreviewSummary.textContent = `${title} · ${meta}`;
  }
}

function promptEditSaveMode(review = null, options = {}) {
  if (!editSaveModeModal) {
    return Promise.resolve(options?.target === "analysis-reference" ? "overwrite" : "new_version");
  }
  if (pendingEditSaveModeResolver) {
    return Promise.resolve(null);
  }
  editSaveModeModal.dataset.mode = options?.target === "analysis-reference" ? "analysis-reference" : "save";
  renderEditReview(review || buildEditReview(previewFrame.contentDocument, previewDocumentHtmlForSave(previewFrame.contentDocument)));
  setEditSaveModeModalCopy(options);
  if (editSaveModeNewVersionButton) {
    editSaveModeNewVersionButton.hidden = options?.target === "analysis-reference";
  }
  return new Promise((resolve) => {
    pendingEditSaveModeResolver = resolve;
    editSaveModeModal.hidden = false;
    if (options?.target === "analysis-reference") {
      editSaveModeOverwriteButton?.focus();
    } else {
      editSaveModeNewVersionButton?.focus();
    }
  });
}

function resolveEditSaveMode(mode) {
  closeEditSaveModeModal(mode);
}

function closeEditSaveModeModal(mode = null) {
  if (editSaveModeModal) editSaveModeModal.hidden = true;
  editSaveModeModal?.removeAttribute("data-mode");
  if (editSaveModeNewVersionButton) editSaveModeNewVersionButton.hidden = false;
  if (!pendingEditSaveModeResolver) return;
  trackUserEvent("manual_edit_save_mode_selected", { selectedName, analysisReferenceId: selectedAnalysisReferenceId, mode: mode || "cancel" });
  const resolve = pendingEditSaveModeResolver;
  pendingEditSaveModeResolver = null;
  resolve(mode);
}

function setEditSaveModeModalCopy(options = {}) {
  const isAnalysisReference = options?.target === "analysis-reference";
  if (editSaveModeTitle) editSaveModeTitle.textContent = isAnalysisReference ? "현황 분석 편집 저장을 확인해 주세요" : "편집 저장 방식을 선택해 주세요";
  if (editSaveModeSubcopy) {
    editSaveModeSubcopy.textContent = isAnalysisReference
      ? "현황 분석 문서는 버전 파일을 새로 만들지 않고 현재 HTML에 바로 반영합니다."
      : "수정한 내용을 새 버전으로 남길지, 현재 버전에 바로 반영할지 선택할 수 있습니다.";
  }
  const overwriteTitle = editSaveModeOverwriteButton?.querySelector("span");
  if (overwriteTitle) overwriteTitle.textContent = isAnalysisReference ? "현황 분석에 바로 반영" : "기존 버전에 수정";
}

function buildEditReview(doc, editedHtml) {
  const currentText = cleanWorkspaceText(doc.body?.innerText || doc.body?.textContent || "");
  const oldText = editingOriginalText || "";
  const delta = currentText.length - oldText.length;
  const findings = validateEditedDocument(doc);
  return {
    htmlChars: editedHtml.length,
    textChars: currentText.length,
    delta,
    findings,
    blockingCount: findings.filter((item) => item.blocking).length,
    warningCount: findings.filter((item) => !item.blocking).length,
  };
}

function renderEditReview(review) {
  if (!review) return;
  if (editReviewSummary) {
    const sign = review.delta > 0 ? "+" : "";
    const issuePhrase = review.delta === 0 && review.findings.length
      ? `기존 문서 기준 검증 이슈 ${review.findings.length}건입니다.`
      : `검증 이슈 ${review.findings.length}건입니다.`;
    editReviewSummary.textContent = `본문 ${review.textChars.toLocaleString()}자, 문서 차이 ${sign}${review.delta.toLocaleString()}자, ${issuePhrase}`;
  }
  if (editReviewFindings) {
    if (!review.findings.length) {
      editReviewFindings.classList.add("empty");
      editReviewFindings.innerHTML = "저장 전 검증에서 발견된 이슈가 없습니다.";
    } else {
      editReviewFindings.classList.remove("empty");
      editReviewFindings.innerHTML = review.findings
        .map((item) => `<div class="edit-review-finding ${item.blocking ? "blocking" : "warn"}"><span>${item.blocking ? "Critical" : "Check"}</span><strong>${escapeHtml(item.targetLabel || item.type)}</strong><p>${escapeHtml(item.message)}</p></div>`)
        .join("");
    }
  }
  if (editSaveModeOverwriteButton) {
    const isAnalysisReference = editSaveModeModal?.dataset.mode === "analysis-reference";
    editSaveModeOverwriteButton.disabled = review.blockingCount > 0;
    editSaveModeOverwriteButton.classList.toggle("disabled", review.blockingCount > 0);
    const label = editSaveModeOverwriteButton.querySelector("strong");
    if (label) {
      label.textContent = review.blockingCount > 0
        ? isAnalysisReference
          ? "Critical 검증 이슈가 있어 현황 분석 저장이 제한됩니다."
          : "Critical 검증 이슈가 있어 덮어쓰기는 제한됩니다. 새 버전으로 저장해 주세요."
        : isAnalysisReference
          ? "현재 현황 분석 HTML 파일을 그대로 덮어씁니다."
          : "현재 버전 파일을 그대로 덮어쓰고 문서 히스토리에 수정 이력을 남깁니다.";
    }
  }
}

function validateEditedDocument(doc) {
  const findings = [];
  const stateNames = collectTableColumnValues(doc, "state", "상태명");
  const functionIds = collectTableColumnValues(doc, "function", "기능 ID");
  const policyIds = collectTableColumnValues(doc, "policy", "정책 ID");
  doc.querySelectorAll("table").forEach((table) => {
    const info = detectEditorTableInfo(table);
    if (info.key === "generic") return;
    const rows = tableBodyRows(table);
    const idHeader = idHeaderForTable(info.key);
    const ids = [];
    rows.forEach((row, rowIndex) => {
      const cells = [...row.querySelectorAll("td, th")];
      info.requiredHeaders.forEach((header) => {
        const index = info.headers.indexOf(header);
        if (index < 0) return;
        if (!cleanWorkspaceText(cells[index]?.textContent || "")) {
          findings.push({
            type: "required-cell",
            targetLabel: `${info.type} ${rowIndex + 1}행`,
            message: `${header} 값이 비어 있습니다.`,
            blocking: true,
          });
        }
      });
      if (idHeader) {
        const idIndex = info.headers.indexOf(idHeader);
        const idValue = cleanWorkspaceText(cells[idIndex]?.textContent || "");
        if (idValue) ids.push({ id: idValue, row: rowIndex + 1, tableType: info.type });
      }
      if (info.key === "transition") {
        ["현재 상태", "다음 상태"].forEach((header) => {
          const index = info.headers.indexOf(header);
          const state = cleanWorkspaceText(cells[index]?.textContent || "");
          if (state && stateNames.length && !stateNames.includes(state)) {
            findings.push({
              type: "state-mismatch",
              targetLabel: `${info.type} ${rowIndex + 1}행`,
              message: `${header} '${state}'가 상태 코드표의 상태명과 일치하지 않습니다.`,
              blocking: true,
            });
          }
        });
      }
      if (info.key === "process") {
        const functionIndex = info.headers.indexOf("관련 기능");
        const policyIndex = info.headers.indexOf("관련 정책");
        const rowLabel = cleanWorkspaceText(cells[0]?.textContent || `${rowIndex + 1}행`);
        validateRelatedIds(findElementIds(cells[functionIndex]?.textContent || "", "FN"), functionIds, "기능", rowLabel, findings);
        validateRelatedIds(findElementIds(cells[policyIndex]?.textContent || "", "PG"), policyIds, "정책", rowLabel, findings);
      }
    });
    duplicateIds(ids).forEach((item) => {
      findings.push({
        type: "duplicate-id",
        targetLabel: item.tableType,
        message: `${item.id} ID가 ${item.rows.join(", ")}행에 중복되어 있습니다.`,
        blocking: true,
      });
    });
  });
  return findings.slice(0, 30);
}

function tableBodyRows(table) {
  return [...(table.querySelector("tbody")?.querySelectorAll("tr") || table.querySelectorAll("tr"))].filter((row) => {
    return row.querySelector("td") && !row.closest("thead");
  });
}

function idHeaderForTable(key) {
  return {
    usecase: "유즈케이스 ID",
    state: "상태 코드",
    process: "프로세스 ID",
    function: "기능 ID",
    policy: "정책 ID",
  }[key] || "";
}

function collectTableColumnValues(doc, key, header) {
  const values = [];
  doc.querySelectorAll("table").forEach((table) => {
    const info = detectEditorTableInfo(table);
    if (info.key !== key) return;
    const index = info.headers.indexOf(header);
    if (index < 0) return;
    tableBodyRows(table).forEach((row) => {
      const value = cleanWorkspaceText(row.querySelectorAll("td, th")[index]?.textContent || "");
      if (value) values.push(value);
    });
  });
  return values;
}

function duplicateIds(items) {
  const rowsById = new Map();
  items.forEach((item) => {
    const key = item.id.toUpperCase();
    rowsById.set(key, [...(rowsById.get(key) || []), item]);
  });
  return [...rowsById.entries()]
    .filter(([, rows]) => rows.length > 1)
    .map(([id, rows]) => ({ id, rows: rows.map((row) => row.row), tableType: rows[0].tableType }));
}

function findElementIds(text, prefix) {
  const pattern = new RegExp(`\\b${prefix}[-_ ]?\\d+\\b`, "gi");
  return [...String(text || "").matchAll(pattern)].map((match) => match[0].toUpperCase().replace(/[ _]/g, "-"));
}

function validateRelatedIds(ids, validIds, label, rowLabel, findings) {
  if (!ids.length) {
    findings.push({
      type: "missing-link",
      targetLabel: rowLabel,
      message: `관련 ${label} ID가 비어 있습니다.`,
      blocking: false,
    });
    return;
  }
  const normalizedValid = validIds.map((id) => id.toUpperCase().replace(/[ _]/g, "-"));
  ids.forEach((id) => {
    if (!normalizedValid.includes(id)) {
      findings.push({
        type: "broken-link",
        targetLabel: rowLabel,
        message: `관련 ${label} ID '${id}'가 ${label} 목록에 없습니다.`,
        blocking: true,
      });
    }
  });
}

async function requestAgentRevision() {
  if (!guardWritePermission("조회 권한은 Agent 수정 요청을 실행할 수 없습니다.")) return;
  if (selectedDraft) {
    await requestDraftRevision();
    return;
  }
  if (!selectedName) return;
  if (selectedPolicyCompleted()) {
    setMessage("작성 완료 상태에서는 '작성 완료 취소' 후에만 Agent 수정 요청을 할 수 있습니다.", true);
    return;
  }
  const instruction = revisionRequest.value.trim();
  if (!instruction) {
    setMessage("수정 요청 내용을 입력해 주세요.", true);
    return;
  }
  await startRevisionRequest(instruction, null, revisionButton);
}

async function requestDraftRevision() {
  if (!selectedDraft) return;
  if (!guardWritePermission("조회 권한은 초안 보완 요청을 실행할 수 없습니다.")) return;
  const instruction = revisionRequest.value.trim();
  if (!instruction) {
    setMessage("작성 중단된 초안에 반영할 보완 요청 내용을 입력해 주세요.", true);
    return;
  }
  if (!selectedDraft?.checkpoint?.path && !selectedDraft?.resumeFrom) {
    setMessage("재개할 체크포인트를 찾을 수 없습니다.", true);
    return;
  }
  if (revisionButton) revisionButton.disabled = true;
  setMessage("보완 요청을 반영해 중단된 지점부터 이어서 작성합니다.");
  await startResumeRequest({
    topic: selectedDraft.topic,
    templateType: selectedDraft.templateType || "simple",
    reviewMode: selectedDraft.reviewMode || "auto",
    inspectionMode: selectedDraft.inspectionMode || "chapter-final",
    writerMode: getSelectedWriterMode(),
    checkpointPath: selectedDraft.resumeFrom || selectedDraft.checkpoint.path,
    brief: `중단된 초안 보완 요청: ${instruction}`,
  });
}

async function requestSelectedRevision() {
  if (!guardWritePermission("조회 권한은 선택 영역 수정을 실행할 수 없습니다.")) return;
  if (!selectedName || !selectedRevisionTarget) {
    setMessage("수정할 문서 영역을 먼저 드래그해서 선택해 주세요.", true);
    closeSelectionRevisionModal();
    return;
  }
  if (selectedPolicyCompleted()) {
    setMessage("작성 완료 상태에서는 '작성 완료 취소' 후에만 선택 영역을 수정할 수 있습니다.", true);
    closeSelectionRevisionModal();
    return;
  }
  const instruction = selectionRevisionRequest.value.trim();
  if (!instruction) {
    setMessage("선택 영역을 어떻게 수정할지 입력해 주세요.", true);
    selectionRevisionRequest.focus();
    return;
  }
  if (getSelectedRevisionMode() === "suggestion") {
    createEditorSuggestion(instruction, selectedRevisionTarget);
    closeSelectionRevisionModal();
    clearPreviewSelection();
    setMessage("선택 영역 제안을 Co-work 패널에 생성했습니다. 직접 편집 모드에서 적용하거나 수정 요청에 담을 수 있습니다.");
    return;
  }
  const started = await startRevisionRequest(instruction, selectedRevisionTarget, selectionRevisionSubmitButton);
  if (started) {
    closeSelectionRevisionModal();
    clearPreviewSelection();
  }
}

function inlineSelectionInstruction() {
  return String(selectionInlineRequest?.value || "").trim();
}

async function requestInlineSelectedRevision() {
  if (!guardWritePermission("조회 권한은 선택 영역 수정을 실행할 수 없습니다.")) return;
  if (!selectedName || !selectedRevisionTarget) {
    setMessage("수정할 문서 영역을 먼저 드래그해서 선택해 주세요.", true);
    return;
  }
  if (selectedPolicyCompleted()) {
    setMessage("작성 완료 상태에서는 '작성 완료 취소' 후에만 선택 영역을 수정할 수 있습니다.", true);
    return;
  }
  const instruction = inlineSelectionInstruction();
  if (!instruction) {
    selectionInlineRequest?.focus();
    setMessage("선택 영역을 어떻게 수정할지 입력해 주세요.", true);
    return;
  }
  const started = await startRevisionRequest(instruction, selectedRevisionTarget, selectionInlineAiButton);
  if (started) clearPreviewSelection();
}

async function addInlineSelectionComment() {
  if (!selectedName && !selectedDraft) {
    setMessage("코멘트를 남길 문서를 먼저 선택해 주세요.", true);
    return;
  }
  if (!selectedRevisionTarget) {
    setMessage("코멘트를 남길 문서 영역을 먼저 드래그해서 선택해 주세요.", true);
    return;
  }
  const note = inlineSelectionInstruction();
  if (!note) {
    selectionInlineRequest?.focus();
    setMessage("선택 영역에 남길 코멘트를 입력해 주세요.", true);
    return;
  }
  setWorkspaceAssistTab("human");
  await addEditorCommentFromCurrentContext(note, { allowSelectedArea: true });
  clearPreviewSelection();
}

function getSelectedRevisionMode() {
  return selectionRevisionModeInputs.find((input) => input.checked)?.value || "suggestion";
}

function updateSelectionRevisionSubmitLabel() {
  if (!selectionRevisionSubmitButton) return;
  selectionRevisionSubmitButton.textContent = getSelectedRevisionMode() === "agent" ? "선택 영역 수정 Agent 실행" : "제안 카드 생성";
}

function revisionSaveModeForRequest(selection) {
  return selection ? "current_version" : "new_version";
}

async function startRevisionRequest(instruction, selection = null, sourceButton = revisionButton) {
  if (!selectedName) return false;
  if (!guardWritePermission("조회 권한은 Agent 수정 요청을 실행할 수 없습니다.")) return false;
  if (selectedPolicyCompleted()) {
    setMessage("작성 완료 상태에서는 '작성 완료 취소' 후에만 Agent 수정 요청을 할 수 있습니다.", true);
    return false;
  }
  const saveMode = revisionSaveModeForRequest(selection);
  let payload;
  try {
    payload = await buildLlmControlledPayload({
      name: selectedName,
      instruction,
      selection,
      saveMode,
      author: document.querySelector("#author")?.value || "Policy Web",
    });
    if (!payload) return false;
  } catch (error) {
    setMessage(error.message || "LLM 사용 인증에 실패했습니다.", true);
    return false;
  }
  if (sourceButton) sourceButton.disabled = true;
  if (revisionButton) revisionButton.disabled = true;
  if (selectionRevisionSubmitButton) selectionRevisionSubmitButton.disabled = true;
  if (selectionInlineAiButton) selectionInlineAiButton.disabled = true;
  if (selectionInlineCommentButton) selectionInlineCommentButton.disabled = true;
  setMessage(
    saveMode === "current_version"
      ? "선택 영역 수정 Agent 작업을 시작합니다. 작은 수정은 현재 버전에 누적 반영합니다."
      : "수정 Agent 작업을 시작합니다."
  );
  try {
    const response = await fetch(apiPath("/api/policies/revise"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "수정 요청에 실패했습니다.");
    }
    activeJobId = data.job.id;
    openProgressModal(data.job);
    startProgressPolling(activeJobId);
    return true;
  } catch (error) {
    setMessage(error.message, true);
    if (revisionButton) revisionButton.disabled = false;
    if (selectionRevisionSubmitButton) selectionRevisionSubmitButton.disabled = false;
    if (selectionInlineAiButton) selectionInlineAiButton.disabled = false;
    if (selectionInlineCommentButton) selectionInlineCommentButton.disabled = false;
    if (sourceButton) sourceButton.disabled = false;
    return false;
  }
}

function showWorkspaceAssistLoading(text) {
  if (!workspaceAssistPanel) return;
  if (!workspaceAssistEnabled) {
    hideWorkspaceAssistPanel();
    return;
  }
  showWorkspaceAssistPanel();
  setAssistList(aiCommentList, [{ level: "good", title: "문서 분석 준비", body: text || "미리보기 로딩이 끝나면 자동으로 갱신됩니다." }]);
  setAssistList(policyValueList, []);
  setAssistList(tbdList, []);
  setAssistList(historyList, []);
  renderEditorAssistPanels();
  setAssistCount(aiCommentCount, 1);
  setAssistCount(policyValueCount, 0);
  setAssistCount(tbdCount, 0);
  setAssistCount(historyCount, 0);
}

function hideWorkspaceAssistPanel() {
  if (workspaceAssistPanel) workspaceAssistPanel.hidden = true;
  resultsLayout?.classList.remove("has-assist");
  updateCommentWorkspaceToolsVisibility();
}

function renderWorkspaceAssistEmpty(text) {
  if (!workspaceAssistPanel) return;
  if (!workspaceAssistEnabled) {
    hideWorkspaceAssistPanel();
    return;
  }
  showWorkspaceAssistPanel();
  setAssistList(aiCommentList, [{ level: "warn", title: "확인할 문서 없음", body: text || "미리보기 문서를 먼저 선택해 주세요." }]);
  setAssistList(policyValueList, []);
  setAssistList(tbdList, []);
  setAssistList(historyList, []);
  renderEditorAssistPanels();
  setAssistCount(aiCommentCount, 1);
  setAssistCount(policyValueCount, 0);
  setAssistCount(tbdCount, 0);
  setAssistCount(historyCount, 0);
}

function updateWorkspaceAssistPanel() {
  if (!workspaceAssistPanel) return;
  if (!workspaceAssistEnabled) {
    hideWorkspaceAssistPanel();
    return;
  }
  if (!selectedName && !selectedDraft) {
    hideWorkspaceAssistPanel();
    return;
  }

  let doc;
  try {
    doc = previewFrame?.contentDocument;
  } catch (error) {
    renderWorkspaceAssistEmpty("미리보기 문서에 접근할 수 없습니다.");
    return;
  }
  if (!doc || !doc.body) {
    renderWorkspaceAssistEmpty("미리보기 문서를 아직 불러오지 못했습니다.");
    return;
  }

  const policyValues = collectPolicyValues(doc);
  const tbdItems = collectTbdItems(doc, policyValues);
  const historyItems = collectHistoryItems(doc);
  const comments = buildWorkspaceComments(doc, policyValues, tbdItems, historyItems);

  showWorkspaceAssistPanel();
  setAssistList(aiCommentList, comments);
  setPolicyValueList(policyValueList, policyValues.slice(0, 12));
  setAssistList(tbdList, tbdItems.slice(0, 8));
  setAssistList(historyList, historyItems.slice(0, 6));
  renderEditorAssistPanels();
  setAssistCount(aiCommentCount, comments.length);
  setAssistCount(policyValueCount, policyValues.length);
  setAssistCount(tbdCount, tbdItems.length);
  setAssistCount(historyCount, historyItems.length);
}

function openDocumentQaReviewModal() {
  if (documentQaReviewModal) {
    documentQaReviewModal.hidden = false;
  }
  if (documentQaReviewInFlight) {
    renderDocumentQaLoading();
    if (documentQaReviewStartButton) {
      documentQaReviewStartButton.disabled = true;
    }
    return;
  }
  const cachedReport = cachedQaReviewReport();
  if (cachedReport) {
    renderDocumentQaReport(cachedReport);
    return;
  }
  renderDocumentQaIntro();
}

async function startDocumentQaReview() {
  if (!selectedName) {
    renderDocumentQaLoading();
    renderDocumentQaError("검수할 정책서를 먼저 선택해 주세요.");
    return;
  }
  let payload;
  try {
    payload = await buildLlmControlledPayload({ name: selectedName });
    if (!payload) {
      renderDocumentQaIntro();
      return;
    }
  } catch (error) {
    renderDocumentQaError(error.message || "LLM 사용 인증에 실패했습니다.");
    return;
  }
  documentQaReviewInFlight = true;
  renderDocumentQaLoading();
  trackUserEvent("document_qa_review_started", { selectedName, writerMode: getSelectedWriterMode() });
  if (documentQaReviewButton) documentQaReviewButton.disabled = true;
  if (documentQaReviewStartButton) documentQaReviewStartButton.disabled = true;
  try {
    const response = await fetch(apiPath("/api/policies/dev-qa-review"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "개발/QA 검수 중 오류가 발생했습니다.");
    }
    if (selectedName) {
      qaReviewReportsByPolicy.set(selectedName, data.report);
    }
    renderDocumentQaReport(data.report);
  } catch (error) {
    renderDocumentQaError(error.message);
  } finally {
    documentQaReviewInFlight = false;
    if (documentQaReviewButton) documentQaReviewButton.disabled = false;
    if (documentQaReviewStartButton) documentQaReviewStartButton.disabled = false;
  }
}

function closeDocumentQaReviewModal() {
  if (isDocumentQaReviewRunning()) {
    const confirmed = window.confirm(
      "개발/QA 검수가 아직 진행 중입니다.\n창을 닫아도 검수 요청은 백그라운드에서 계속 진행될 수 있습니다.\n그래도 닫을까요?"
    );
    if (!confirmed) return false;
  }
  stopDocumentQaLoadingTimer();
  if (documentQaReviewModal) {
    documentQaReviewModal.hidden = true;
  }
  return true;
}

function isDocumentQaReviewRunning() {
  return documentQaReviewInFlight || documentQaReviewModal?.dataset.mode === "loading";
}

function renderDocumentQaIntro() {
  latestQaReviewReport = null;
  stopDocumentQaLoadingTimer();
  setDocumentQaMode("intro");
  if (documentQaReviewSummary) {
    documentQaReviewSummary.textContent = "검수 시작 전, Development QA Review Agent가 확인할 기준을 먼저 보여드립니다.";
  }
  if (documentQaReviewStartButton) {
    documentQaReviewStartButton.hidden = false;
    documentQaReviewStartButton.disabled = false;
    documentQaReviewStartButton.textContent = "검수 시작";
  }
  if (documentQaActionCheckButton) {
    documentQaActionCheckButton.hidden = true;
    documentQaActionCheckButton.disabled = true;
  }
  renderDocumentQaStatus({
    label: "검수 범위",
    value: "개발·QA 준비도 확인",
    message: selectedName
      ? "검수 시작을 누르면 현재 선택한 정책서가 개발 상세 설계와 QA 테스트 설계에 충분한지 확인하고, 보완 항목을 변경·추가·삭제 유형으로만 정리합니다."
      : "문서 작업실에서 정책서를 선택한 뒤 검수 시작을 누를 수 있습니다.",
    status: selectedName ? "info" : "warn",
  });
  setQaList(
    devFindingList,
    devFindingCount,
    [
      "유즈케이스 → 프로세스 → 기능 → 정책 연결이 개발자가 구현 단위로 해석 가능할지 확인합니다.",
      "BSS/연계 시스템의 판정, 상태 반영, 이력 저장, 결과 회신 기준이 빠지지 않았는지 확인합니다.",
      "정책이 기능 설명이 아니라 실제 동작 기준값과 제한 조건으로 작성됐는지 확인하고 변경/추가/삭제 항목으로 정리합니다.",
    ],
    "검수 기준을 준비 중입니다.",
    { countLabel: "검수 전" }
  );
  setQaList(
    qaFindingList,
    qaFindingCount,
    [
      "정상, 예외, 제한, 보류, 실패 흐름에서 QA 시나리오를 도출할 수 있는지 확인합니다.",
      "상태 전이와 정책 경계값이 테스트 케이스로 검증 가능한 수준인지 확인합니다.",
      "회귀 영향과 운영 확인 포인트가 문서에 드러나는지 확인하고 우선순위를 표시합니다.",
    ],
    "검수 기준을 준비 중입니다.",
    { countLabel: "검수 전" }
  );
  setQaList(qaActionList, qaActionCount, [], "검수 완료 후 보완 권고가 표시됩니다.", { countLabel: "검수 전" });
  setQaList(qaGapList, qaGapCount, [], "검수 완료 후 근거 Gap이 표시됩니다.", { countLabel: "검수 전" });
  renderQaCoverage([
    { item: "구조 연결성", status: "warn", detail: "액터, 유즈케이스, 상태, 프로세스, 기능, 정책 연결을 확인합니다." },
    { item: "개발 충분성", status: "warn", detail: "상세 설계자가 구현 범위와 판단 기준을 이해할 수 있는지 확인합니다." },
    { item: "QA 충분성", status: "warn", detail: "테스트 케이스와 경계 조건을 도출할 수 있는지 확인합니다." },
  ]);
  updateDocumentQaRevisionState();
}

function renderDocumentQaLoading() {
  latestQaReviewReport = null;
  setDocumentQaMode("loading");
  startDocumentQaLoadingTimer();
  if (documentQaReviewSummary) {
    documentQaReviewSummary.textContent = "Development QA Review Agent가 문서를 읽고 개발·QA 준비도를 검수하고 있습니다.";
  }
  if (documentQaReviewStartButton) {
    documentQaReviewStartButton.textContent = "검수 중";
  }
  if (documentQaActionCheckButton) {
    documentQaActionCheckButton.disabled = true;
  }
  renderDocumentQaStatus({
    label: "검수 중",
    value: "처리 중",
    message: "정책 구조, 상태 전이, 프로세스-기능-정책 연결, QA 시나리오 도출 가능성을 확인합니다.",
    status: "loading",
  });
  setQaList(devFindingList, devFindingCount, [], "검수 결과를 기다리고 있습니다.");
  setQaList(qaFindingList, qaFindingCount, [], "검수 결과를 기다리고 있습니다.");
  setQaList(qaActionList, qaActionCount, [], "보완 권고를 정리하고 있습니다.");
  setQaList(qaGapList, qaGapCount, [], "근거 Gap을 확인하고 있습니다.");
  renderQaCoverage([]);
  updateDocumentQaRevisionState();
}

function renderDocumentQaError(message) {
  latestQaReviewReport = null;
  stopDocumentQaLoadingTimer();
  setDocumentQaMode("intro");
  if (documentQaReviewSummary) {
    documentQaReviewSummary.textContent = "개발/QA 검수를 완료하지 못했습니다.";
  }
  if (documentQaReviewStartButton) {
    documentQaReviewStartButton.textContent = cachedQaReviewReport() ? "재검수 요청" : "검수 시작";
  }
  if (documentQaActionCheckButton) {
    documentQaActionCheckButton.hidden = !cachedQaReviewReport();
    documentQaActionCheckButton.disabled = true;
  }
  renderDocumentQaStatus({
    label: "검수 실패",
    value: "오류",
    message,
    status: "danger",
  });
  setQaList(devFindingList, devFindingCount, [], "검수 결과가 없습니다.");
  setQaList(qaFindingList, qaFindingCount, [], "검수 결과가 없습니다.");
  setQaList(qaActionList, qaActionCount, [message], "보완 권고가 없습니다.");
  setQaList(qaGapList, qaGapCount, [], "근거 Gap이 없습니다.");
  renderQaCoverage([]);
  updateDocumentQaRevisionState();
}

function renderDocumentQaReport(report) {
  const safeReport = report || {};
  latestQaReviewReport = safeReport;
  setDocumentQaLoadingProgressValue(100);
  stopDocumentQaLoadingTimer();
  setDocumentQaMode("result");
  if (selectedName) {
    qaReviewReportsByPolicy.set(selectedName, safeReport);
  }
  if (documentQaReviewSummary) {
    documentQaReviewSummary.textContent = "검수 결과를 확인하고 필요한 보완 항목을 선택해 요청할 수 있습니다.";
  }
  if (documentQaReviewStartButton) {
    documentQaReviewStartButton.hidden = false;
    documentQaReviewStartButton.disabled = false;
    documentQaReviewStartButton.textContent = "재검수 요청";
  }
  if (documentQaActionCheckButton) {
    documentQaActionCheckButton.hidden = false;
    documentQaActionCheckButton.disabled = !hasQaActionItems(safeReport);
  }
  renderDocumentQaStatus({
    label: "검토 결과",
    value: "",
    message: safeReport.summary || "개발/QA 관점 검수를 완료했습니다.",
    status: qaVerdictStatus(safeReport),
  });
  setQaList(devFindingList, devFindingCount, safeReport.development_findings || [], "개발 관점에서 발견된 이슈가 없습니다.", { selectable: true, group: "development" });
  setQaList(qaFindingList, qaFindingCount, safeReport.qa_findings || [], "QA 관점에서 발견된 이슈가 없습니다.", { selectable: true, group: "qa" });
  setQaList(qaActionList, qaActionCount, safeReport.recommended_actions || [], "보완 권고가 없습니다.");
  setQaList(qaGapList, qaGapCount, safeReport.evidence_gaps || [], "근거 Gap이 없습니다.");
  renderQaCoverage(safeReport.coverage_checks || []);
  renderDocumentQaResultScreen(safeReport);
  updateDocumentQaRevisionState();
}

function setDocumentQaMode(mode) {
  if (documentQaReviewModal) {
    documentQaReviewModal.dataset.mode = mode;
    const modalSurface = documentQaReviewModal.querySelector(".document-qa-modal");
    if (modalSurface) {
      modalSurface.dataset.mode = mode;
    }
  }
  document.querySelectorAll("[data-qa-intro]").forEach((node) => {
    node.hidden = mode !== "intro";
  });
  if (documentQaLoadingPanel) {
    documentQaLoadingPanel.hidden = mode !== "loading";
  }
  if (documentQaResultStats) {
    documentQaResultStats.hidden = mode !== "result";
  }
  if (documentQaResultSection) {
    documentQaResultSection.hidden = mode !== "result";
  }
  if (documentQaFooter) {
    documentQaFooter.hidden = mode !== "result";
  }
}

function startDocumentQaLoadingTimer() {
  stopDocumentQaLoadingTimer();
  documentQaLoadingStartedAt = Date.now();
  renderDocumentQaLoadingProgress();
  documentQaLoadingTimer = window.setInterval(renderDocumentQaLoadingProgress, 1000);
}

function stopDocumentQaLoadingTimer() {
  if (documentQaLoadingTimer) {
    window.clearInterval(documentQaLoadingTimer);
    documentQaLoadingTimer = null;
  }
}

function renderDocumentQaLoadingProgress() {
  const elapsedSeconds = documentQaLoadingStartedAt
    ? Math.max(0, Math.floor((Date.now() - documentQaLoadingStartedAt) / 1000))
    : 0;
  const currentIndex = currentDocumentQaLoadingStepIndex(elapsedSeconds);
  const currentStep = DOCUMENT_QA_LOADING_STEPS[currentIndex] || DOCUMENT_QA_LOADING_STEPS[0];
  const progress = documentQaEstimatedProgress(elapsedSeconds);

  setDocumentQaLoadingProgressValue(progress);
  if (documentQaLoadingPolicy) documentQaLoadingPolicy.textContent = selectedName || "-";
  if (documentQaLoadingElapsed) documentQaLoadingElapsed.textContent = formatElapsedTime(elapsedSeconds);
  if (documentQaLoadingCurrent) documentQaLoadingCurrent.textContent = currentStep?.label || "검수 중";
  renderDocumentQaLoadingSteps(currentIndex);
}

function documentQaEstimatedProgress(elapsedSeconds) {
  if (elapsedSeconds <= 0) return 4;
  if (elapsedSeconds <= 90) {
    return Math.min(88, Math.max(4, Math.round((elapsedSeconds / 90) * 88)));
  }
  if (elapsedSeconds <= 210) {
    return Math.min(97, 88 + Math.floor((elapsedSeconds - 90) / 15));
  }
  return Math.min(99, 97 + Math.floor((elapsedSeconds - 210) / 90));
}

function setDocumentQaLoadingProgressValue(progress) {
  const safeProgress = Math.max(0, Math.min(100, Math.round(Number(progress) || 0)));
  if (documentQaLoadingPercent) documentQaLoadingPercent.textContent = `${safeProgress}%`;
  if (documentQaLoadingBar) documentQaLoadingBar.style.width = `${safeProgress}%`;
}

function currentDocumentQaLoadingStepIndex(elapsedSeconds) {
  let activeIndex = 0;
  DOCUMENT_QA_LOADING_STEPS.forEach((step, index) => {
    if (elapsedSeconds >= step.start) {
      activeIndex = index;
    }
  });
  return activeIndex;
}

function renderDocumentQaLoadingSteps(activeIndex) {
  if (!documentQaLoadingSteps) return;
  documentQaLoadingSteps.innerHTML = "";
  DOCUMENT_QA_LOADING_STEPS.forEach((step, index) => {
    const item = document.createElement("li");
    item.className = index < activeIndex ? "done" : index === activeIndex ? "active" : "waiting";
    const marker = document.createElement("span");
    marker.className = "document-qa-loading-marker";
    marker.textContent = String(index + 1).padStart(2, "0");
    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = step.label;
    const detail = document.createElement("p");
    detail.textContent = step.detail;
    body.append(title, detail);
    item.append(marker, body);
    documentQaLoadingSteps.appendChild(item);
  });
}

function formatElapsedTime(seconds) {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function renderDocumentQaResultScreen(report) {
  const items = collectAllQaActionItems(report);
  renderDocumentQaStats(report, items);
  setQaList(documentQaResultList, documentQaResultCount, items, "보완 필요 사항이 없습니다.", { selectable: true });
}

function renderDocumentQaStats(report, items) {
  if (!documentQaResultStats) return;
  const total = items.length;
  const p1Count = items.filter((item) => item.priority === "P1").length;
  const developmentCount = items.filter((item) => item.perspective === "development").length;
  const qaCount = items.filter((item) => item.perspective === "qa").length;
  const changeCount = items.filter((item) => item.action_type === "change").length;
  const addCount = items.filter((item) => item.action_type === "add").length;
  const deleteCount = items.filter((item) => item.action_type === "delete").length;
  const stats = [
    { label: "검수 점수", value: `${Number(report?.score || 0)}점`, tone: qaVerdictStatus(report) },
    { label: "보완 항목", value: `${total}건`, tone: total ? "warn" : "success" },
    { label: "P1 우선", value: `${p1Count}건`, tone: p1Count ? "danger" : "success" },
    { label: "개발 / QA", value: `${developmentCount} / ${qaCount}`, tone: "info" },
    { label: "변경 / 추가", value: `${changeCount} / ${addCount}`, tone: "info" },
    { label: "삭제", value: `${deleteCount}건`, tone: deleteCount ? "warn" : "info" },
  ];
  documentQaResultStats.innerHTML = "";
  stats.forEach((stat) => {
    const card = document.createElement("article");
    card.className = `document-qa-stat-card ${stat.tone || "info"}`;
    const label = document.createElement("span");
    label.textContent = stat.label;
    const value = document.createElement("strong");
    value.textContent = stat.value;
    card.append(label, value);
    documentQaResultStats.appendChild(card);
  });
}

function renderDocumentQaStatus({ label, value, message, status }) {
  if (!documentQaStatus) return;
  documentQaStatus.className = `document-qa-status-card ${status || ""}`.trim();
  documentQaStatus.innerHTML = "";
  const labelEl = document.createElement("span");
  labelEl.textContent = label || "검수 상태";
  const valueEl = document.createElement("strong");
  valueEl.textContent = value || "-";
  const messageEl = document.createElement("p");
  messageEl.innerHTML = lineBreakAfterSentence(message || "");
  documentQaStatus.append(labelEl);
  if (value) {
    documentQaStatus.append(valueEl);
  }
  documentQaStatus.append(messageEl);
}

function lineBreakAfterSentence(value) {
  return escapeHtml(value)
    .replace(/([.。！？!?])\s+/g, "$1<br/>")
    .replace(/(다\.|요\.|음\.|함\.|됨\.|임\.)\s*/g, "$1<br/>");
}

function setQaList(container, counter, items, emptyText, options = {}) {
  if (counter) {
    counter.textContent = options.countLabel || `${Array.isArray(items) ? items.length : 0}건`;
  }
  if (!container) return;
  container.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    container.className = "document-qa-list empty";
    container.textContent = emptyText;
    return;
  }
  container.className = "document-qa-list";
  items.forEach((item) => {
    const card = document.createElement("article");
    const itemPayload = normalizeQaItemPayload(item, options.group);
    const statusInfo = qaActionStatusFor(itemPayload.item_key);
    if (typeof item === "string") {
      card.className = "document-qa-finding info";
      const title = document.createElement("strong");
      title.textContent = item;
      if (options.selectable) {
        const topline = document.createElement("div");
        topline.className = "document-qa-card-topline document-qa-card-topline-status";
        topline.appendChild(buildQaActionStatusBadge(statusInfo));
        card.appendChild(topline);
      }
      card.appendChild(title);
      if (options.selectable) {
        card.appendChild(buildQaActionRow(itemPayload));
        card.appendChild(buildQaOptionalNote());
      }
      container.appendChild(card);
      return;
    }
    const severity = qaSeverityClass(item.severity);
    card.className = `document-qa-finding ${severity}`;
    const topline = document.createElement("div");
    topline.className = "document-qa-card-topline";
    const metaRow = document.createElement("div");
    metaRow.className = "document-qa-meta-row";
    const perspectiveBadge = document.createElement("span");
    perspectiveBadge.textContent = qaGroupLabel(itemPayload.group || itemPayload.perspective);
    const actionBadge = document.createElement("span");
    actionBadge.className = `document-qa-action ${itemPayload.action_type}`;
    actionBadge.textContent = qaActionLabel(itemPayload.action_type);
    const priorityBadge = document.createElement("span");
    priorityBadge.className = `document-qa-priority ${qaPriorityClass(itemPayload.priority)}`;
    priorityBadge.textContent = itemPayload.priority;
    metaRow.append(perspectiveBadge, actionBadge, priorityBadge);
    topline.append(metaRow);
    if (options.selectable) {
      topline.appendChild(buildQaActionStatusBadge(statusInfo));
    }
    const title = document.createElement("strong");
    title.textContent = item.title || "검토 항목";
    const table = buildQaFindingTable([
      ["상세", item.detail || ""],
      ["권고", item.recommendation || ""],
      ["현재 내용", itemPayload.current_content],
      [qaDesiredLabel(itemPayload.action_type), itemPayload.desired_change],
      ["위치", itemPayload.target_location],
    ]);
    card.append(topline, title, table);
    if (options.selectable) {
      card.appendChild(buildQaActionRow(itemPayload));
      card.appendChild(buildQaOptionalNote());
    }
    container.appendChild(card);
  });
}

function normalizeQaItemPayload(item, group) {
  let payload;
  if (typeof item === "string") {
    payload = {
      group: group || "action",
      severity: "info",
      priority: "P3",
      action_type: "change",
      perspective: group || "action",
      title: item,
      target_location: "문서 본문",
      current_content: "",
      desired_change: item,
      detail: "",
      recommendation: item,
    };
    payload.item_key = qaActionItemKey(payload);
    return payload;
  }
  payload = {
    group: group || item?.perspective || "finding",
    perspective: String(item?.perspective || group || "finding"),
    priority: qaPriorityClass(item?.priority).toUpperCase(),
    action_type: qaActionType(item?.action_type),
    severity: qaSeverityClass(item?.severity),
    title: String(item?.title || "검토 항목"),
    target_location: String(item?.target_location || "문서 본문"),
    current_content: String(item?.current_content || ""),
    desired_change: String(item?.desired_change || item?.recommendation || ""),
    detail: String(item?.detail || ""),
    recommendation: String(item?.recommendation || ""),
  };
  payload.item_key = String(item?.item_key || item?.key || qaActionItemKey(payload));
  return payload;
}

function qaActionItemKey(item) {
  const seed = [
    item.perspective || item.group || "",
    item.priority || "",
    item.action_type || "",
    item.title || "",
    item.target_location || "",
    item.current_content || "",
    item.desired_change || "",
  ].join("|");
  return `qa-${simpleHash(seed)}`;
}

function simpleHash(value) {
  let hash = 0;
  const text = String(value || "");
  for (let index = 0; index < text.length; index += 1) {
    hash = ((hash << 5) - hash + text.charCodeAt(index)) | 0;
  }
  return Math.abs(hash).toString(36);
}

function buildQaActionStatusBadge(statusInfo) {
  const badge = document.createElement("span");
  const status = statusInfo?.status || "unchecked";
  badge.className = `document-qa-action-status ${status}`;
  badge.textContent = qaActionStatusLabel(status);
  if (statusInfo?.evidence) {
    badge.title = statusInfo.evidence;
  }
  return badge;
}

function buildQaActionRow(payload) {
  const row = document.createElement("div");
  row.className = "document-qa-action-row";
  row.appendChild(buildQaSelectableControl(payload));
  return row;
}

function qaActionStatusLabel(status) {
  return {
    unchecked: "조치 미확인",
    requested: "보완 요청됨",
    checking: "확인 중",
    resolved: "조치 완료",
    partial: "부분 반영",
    open: "미조치",
    error: "확인 오류",
  }[status] || "조치 미확인";
}

function qaActionStatusFor(itemKey, name = selectedName) {
  const statusMap = loadQaActionStatusMap(name);
  return statusMap[itemKey] || { status: "unchecked", evidence: "", note: "" };
}

function loadQaActionStatusMap(name = selectedName) {
  if (!name) return {};
  try {
    return JSON.parse(window.localStorage.getItem(qaActionStatusStorageKey(name)) || "{}") || {};
  } catch (error) {
    return {};
  }
}

function saveQaActionStatusMap(name, statusMap) {
  if (!name) return;
  window.localStorage.setItem(qaActionStatusStorageKey(name), JSON.stringify(statusMap || {}));
}

function qaActionStatusStorageKey(name) {
  return `ncPolicyQaActionStatus:${name}`;
}

function updateQaActionStatuses(name, items, status) {
  const statusMap = loadQaActionStatusMap(name);
  const now = new Date().toISOString();
  (items || []).forEach((item) => {
    const key = item.item_key || item.key;
    if (!key) return;
    statusMap[key] = {
      ...(statusMap[key] || {}),
      status,
      evidence: statusMap[key]?.evidence || "",
      note: statusMap[key]?.note || "",
      updatedAt: now,
    };
  });
  saveQaActionStatusMap(name, statusMap);
}

function applyQaActionCheckResults(name, results) {
  const statusMap = loadQaActionStatusMap(name);
  const now = new Date().toISOString();
  (results || []).forEach((item) => {
    if (!item.item_key) return;
    statusMap[item.item_key] = {
      status: item.status || "open",
      evidence: item.evidence || "",
      note: item.note || "",
      updatedAt: now,
    };
  });
  saveQaActionStatusMap(name, statusMap);
}

function buildQaFact(label, value) {
  const fact = document.createElement("p");
  fact.className = `document-qa-fact${value ? "" : " muted"}`;
  fact.textContent = value ? `${label}: ${value}` : `${label}: 해당 없음`;
  return fact;
}

function buildQaFindingTable(rows) {
  const table = document.createElement("div");
  table.className = "document-qa-finding-table";
  rows.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = `document-qa-finding-row${value ? "" : " muted"}`;
    const labelCell = document.createElement("span");
    labelCell.textContent = label;
    const valueCell = document.createElement("p");
    valueCell.innerHTML = lineBreakAfterSentence(value || "해당 없음");
    row.append(labelCell, valueCell);
    table.appendChild(row);
  });
  return table;
}

function buildQaSelectableControl(payload) {
  const label = document.createElement("label");
  label.className = "document-qa-select-wrap";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.className = "document-qa-select";
  input.dataset.payload = JSON.stringify(payload);
  input.disabled = !canCurrentUserWritePolicies();
  const text = document.createElement("span");
  text.textContent = "보완";
  label.setAttribute("aria-label", "보완 요청에 담기");
  label.title = input.disabled ? "조회 권한은 보완 요청을 실행할 수 없습니다." : "보완 요청에 담기";
  label.append(input, text);
  return label;
}

function buildQaOptionalNote() {
  const label = document.createElement("label");
  label.className = "document-qa-note-field";
  const caption = document.createElement("span");
  caption.className = "document-qa-note-caption";
  caption.textContent = "수정 방향 메모(선택)";
  const textarea = document.createElement("textarea");
  textarea.className = "document-qa-note";
  textarea.rows = 2;
  textarea.placeholder = "예: 정책 상세의 기준값을 더 구체적으로 작성해줘.";
  label.append(caption, textarea);
  return label;
}

function renderQaCoverage(items) {
  if (!qaCoverageList) return;
  qaCoverageList.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "document-qa-empty";
    empty.textContent = "커버리지 체크 결과를 기다리고 있습니다.";
    qaCoverageList.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("article");
    const status = qaCoverageStatus(item.status);
    card.className = `document-qa-check ${status}`;
    const badge = document.createElement("span");
    badge.textContent = qaCoverageLabel(status);
    const title = document.createElement("strong");
    title.textContent = item.item || "점검 항목";
    const detail = document.createElement("p");
    detail.textContent = item.detail || "";
    card.append(badge, title, detail);
    qaCoverageList.appendChild(card);
  });
}

function updateDocumentQaRevisionState() {
  const checked = [...(documentQaReviewModal?.querySelectorAll(".document-qa-select:checked") || [])];
  if (documentQaSelectionSummary) {
    if (!latestQaReviewReport) {
      documentQaSelectionSummary.textContent = "검수 결과에서 보완할 항목을 선택하면 수정 Agent에게 전달할 수 있습니다.";
    } else if (!canCurrentUserWritePolicies()) {
      documentQaSelectionSummary.textContent = "조회 권한은 개발/QA 검수 결과 확인만 가능하며 보완 요청은 실행할 수 없습니다.";
    } else if (checked.length === 0) {
      documentQaSelectionSummary.textContent = "변경·추가·삭제 보완 항목을 체크하고, 필요하면 항목별 수정 방향 메모를 입력하세요.";
    } else {
      documentQaSelectionSummary.textContent = `${checked.length}개 보완 항목을 선택했습니다. 선택 항목만 수정 Agent에게 전달합니다.`;
    }
  }
  if (documentQaRevisionButton) {
    documentQaRevisionButton.disabled = checked.length === 0 || !canCurrentUserWritePolicies();
  }
  if (documentQaActionCheckButton) {
    documentQaActionCheckButton.disabled = !selectedName || !hasQaActionItems(latestQaReviewReport);
  }
}

async function checkDocumentQaActionStatus({ name = selectedName, items = null, manual = false } = {}) {
  const targetItems = items || collectAllQaActionItems(latestQaReviewReport);
  if (!name || targetItems.length === 0) {
    if (manual) {
      setMessage("확인할 보완 요청 항목이 없습니다.", true);
    }
    return false;
  }
  let payload;
  try {
    payload = await buildLlmControlledPayload({ name, items: targetItems });
    if (!payload) return false;
  } catch (error) {
    setMessage(error.message || "LLM 사용 인증에 실패했습니다.", true);
    return false;
  }
  updateQaActionStatuses(name, targetItems, "checking");
  if (latestQaReviewReport && name === selectedName) {
    renderDocumentQaReport(latestQaReviewReport);
  }
  if (documentQaActionCheckButton) documentQaActionCheckButton.disabled = true;
  setMessage(manual ? "보완 여부를 확인하고 있습니다." : "보완 요청 반영 여부를 자동 확인하고 있습니다.");
  try {
    const response = await fetch(apiPath("/api/policies/dev-qa-action-check"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "보완 여부 확인에 실패했습니다.");
    }
    applyQaActionCheckResults(name, data.report.items || []);
    if (name === selectedName && latestQaReviewReport) {
      renderDocumentQaReport(latestQaReviewReport);
    }
    setMessage(data.report.summary || "보완 여부 확인을 완료했습니다.");
    return true;
  } catch (error) {
    updateQaActionStatuses(name, targetItems, "error");
    if (name === selectedName && latestQaReviewReport) {
      renderDocumentQaReport(latestQaReviewReport);
    }
    setMessage(error.message, true);
    return false;
  } finally {
    if (documentQaActionCheckButton) {
      documentQaActionCheckButton.disabled = !selectedName || !hasQaActionItems(latestQaReviewReport);
    }
  }
}

function collectAllQaActionItems(report) {
  if (!report) return [];
  return [
    ...(report.development_findings || []).map((item) => normalizeQaItemPayload(item, "development")),
    ...(report.qa_findings || []).map((item) => normalizeQaItemPayload(item, "qa")),
  ];
}

function hasQaActionItems(report) {
  return collectAllQaActionItems(report).length > 0;
}

async function requestDocumentQaRevision() {
  if (!guardWritePermission("조회 권한은 개발/QA 보완 요청을 실행할 수 없습니다.")) return;
  if (!latestQaReviewReport) {
    renderDocumentQaError("먼저 개발/QA 검수를 실행해 주세요.");
    return;
  }
  const selectedItems = collectSelectedQaRevisionItems();
  if (selectedItems.length === 0) {
    updateDocumentQaRevisionState();
    return;
  }
  updateQaActionStatuses(selectedName, selectedItems, "requested");
  pendingQaActionCheck = { sourceName: selectedName, items: selectedItems, report: latestQaReviewReport };
  renderDocumentQaReport(latestQaReviewReport);
  const instruction = buildQaRevisionInstruction(selectedItems, latestQaReviewReport);
  const started = await startRevisionRequest(instruction, null, documentQaRevisionButton);
  if (started) {
    closeDocumentQaReviewModal();
  } else {
    pendingQaActionCheck = null;
  }
}

function collectSelectedQaRevisionItems() {
  return [...(documentQaReviewModal?.querySelectorAll(".document-qa-select:checked") || [])].map((input, index) => {
    const card = input.closest(".document-qa-finding");
    let payload = {};
    try {
      payload = JSON.parse(input.dataset.payload || "{}");
    } catch (error) {
      payload = {};
    }
    return {
      index: index + 1,
      item_key: payload.item_key || payload.key || "",
      group: payload.group || "finding",
      perspective: payload.perspective || payload.group || "finding",
      priority: payload.priority || "P3",
      action_type: payload.action_type || "change",
      severity: payload.severity || "info",
      title: payload.title || "검토 항목",
      target_location: payload.target_location || "문서 본문",
      current_content: payload.current_content || "",
      desired_change: payload.desired_change || "",
      detail: payload.detail || "",
      recommendation: payload.recommendation || "",
      note: card?.querySelector(".document-qa-note")?.value?.trim() || "",
    };
  });
}

function buildQaRevisionInstruction(items, report) {
  const lines = items.map((item) => {
    const parts = [
      `${item.index}. [${item.priority} / ${qaGroupLabel(item.perspective || item.group)} / ${qaActionLabel(item.action_type)}] ${item.title}`,
      `   - 대상 위치: ${item.target_location}`,
      item.current_content ? `   - 현재 내용: ${item.current_content}` : "",
      item.desired_change ? `   - 원하는 변경: ${item.desired_change}` : "",
      item.detail ? `   - 검수 내용: ${item.detail}` : "",
      item.recommendation ? `   - 권고 방향: ${item.recommendation}` : "",
      item.note ? `   - 사용자 수정 방향 메모: ${item.note}` : "",
    ].filter(Boolean);
    return parts.join("\n");
  });
  return [
    "개발/QA 검수 결과 중 사용자가 선택한 보완 요청만 반영해줘.",
    "각 항목은 변경/추가/삭제 유형을 반드시 지켜서 반영해줘.",
    "전체 문서를 새로 쓰지 말고, 선택된 보완 항목과 관련된 장/항목 중심으로 수정해줘.",
    "수정 후 액터-유즈케이스-상태-프로세스-기능-정책 연결성과 문서 히스토리를 유지해줘.",
    `검수 요약: ${report?.summary || ""}`,
    "선택된 보완 항목:",
    lines.join("\n"),
  ].join("\n\n");
}

function qaGroupLabel(group) {
  return {
    development: "개발 관점",
    qa: "QA 관점",
    action: "보완 권고",
    gap: "근거 Gap",
  }[group] || "검수 항목";
}

function qaActionType(value) {
  const actionType = String(value || "change").toLowerCase();
  if (["change", "add", "delete"].includes(actionType)) return actionType;
  return "change";
}

function qaActionLabel(value) {
  return {
    change: "내용 변경",
    add: "내용 추가",
    delete: "내용 삭제",
  }[qaActionType(value)] || "내용 변경";
}

function qaDesiredLabel(value) {
  return {
    change: "변경 방향",
    add: "추가할 내용",
    delete: "삭제 기준",
  }[qaActionType(value)] || "변경 방향";
}

function qaPriorityClass(value) {
  const priority = String(value || "P3").toUpperCase();
  if (["P1", "P2", "P3"].includes(priority)) return priority.toLowerCase();
  return "p3";
}

function qaPriorityLabel(value) {
  return qaPriorityClass(value).toUpperCase();
}

function qaVerdictStatus(report) {
  const score = Number(report?.score || 0);
  const verdict = String(report?.verdict || "");
  if (verdict === "위험" || score < 70) return "danger";
  if (verdict === "보완 필요" || score < 90) return "warn";
  return "success";
}

function qaSeverityClass(value) {
  const severity = String(value || "info").toLowerCase();
  if (["critical", "major", "minor", "info"].includes(severity)) return severity;
  return "info";
}

function qaSeverityLabel(value) {
  return {
    critical: "Critical",
    major: "Major",
    minor: "Minor",
    info: "Info",
  }[value] || "Info";
}

function qaCoverageStatus(value) {
  const status = String(value || "warn").toLowerCase();
  if (["pass", "warn", "fail"].includes(status)) return status;
  return "warn";
}

function qaCoverageLabel(value) {
  return {
    pass: "Pass",
    warn: "Warn",
    fail: "Fail",
  }[value] || "Warn";
}

function openPiCheckModal() {
  if (piCheckModal) {
    piCheckModal.hidden = false;
  }
  renderPiCheckIntro();
}

function closePiCheckModal() {
  if (piCheckModal) {
    piCheckModal.hidden = true;
  }
}

function updatePiCheckFileState() {
  const asIsFile = piCheckAsIsFileInput?.files?.[0] || null;
  const toBeFile = piCheckToBeFileInput?.files?.[0] || null;
  if (piCheckAsIsFileLabel) {
    piCheckAsIsFileLabel.textContent = asIsFile ? `${asIsFile.name} · ${formatSize(asIsFile.size || 0)}` : "현재/기존 문서 업로드(선택)";
  }
  if (piCheckToBeFileLabel) {
    piCheckToBeFileLabel.textContent = toBeFile ? `${toBeFile.name} · ${formatSize(toBeFile.size || 0)}` : "개선/목표 문서 업로드(필수)";
  }
  if (piCheckStartButton) {
    piCheckStartButton.disabled = !toBeFile || piCheckInFlight;
  }
}

function renderPiCheckIntro() {
  hidePiCheckProgress();
  latestPiCheckReport = null;
  if (piCheckSummary) {
    piCheckSummary.textContent = "PI Playbook과 To-be Flow & KPI 혁신성 Rubric 기준으로 업로드 문서의 프로세스 혁신성, 요구사항 포괄성, KPI, Value Driver, 자동화·AI·CX 기여도를 검수 항목과 검수 방식 기준으로 점검합니다.";
  }
  if (piCheckStats) {
    piCheckStats.hidden = true;
  }
  updatePiCheckFooter(null);
  renderPiCheckStatus({
    label: "PI Check 기준",
    value: "50개 체크 + 안티패턴",
    message: "문서를 업로드하면 항목별 검수 방식, 판정 근거, As-Is 비교, GateKeeper 재검수를 함께 표시합니다.",
    status: "info",
  });
  renderPiCheckComparison(null);
  renderPiCheckItems(piCheckRubric?.checklist || [], { intro: true });
  renderPiCheckAntiPatterns(piCheckRubric?.antiPatterns || piCheckRubric?.anti_patterns || [], { intro: true });
  renderPiCheckRecommendations([]);
  updatePiCheckFileState();
  if (!piCheckRubric && !piCheckRubricLoading) {
    if (piCheckItemList) {
      piCheckItemList.className = "pi-check-list empty";
      piCheckItemList.textContent = "PI Check 체크 항목을 불러오고 있습니다.";
    }
    if (piCheckAntiPatternList) {
      piCheckAntiPatternList.className = "pi-check-list empty";
      piCheckAntiPatternList.textContent = "PI Check 안티패턴 기준을 불러오고 있습니다.";
    }
    loadPiCheckRubric();
  }
}

async function loadPiCheckRubric() {
  piCheckRubricLoading = true;
  try {
    const response = await fetch(apiPath("/api/pi-check-rubric"), { headers: jsonHeaders() });
    const data = await response.json().catch(() => ({}));
    if (response.ok && data.ok) {
      piCheckRubric = data.rubric || null;
      if (!piCheckInFlight && !piCheckModal?.hidden && !latestPiCheckReport) {
        renderPiCheckItems(piCheckRubric?.checklist || [], { intro: true });
        renderPiCheckAntiPatterns(piCheckRubric?.antiPatterns || piCheckRubric?.anti_patterns || [], { intro: true });
      }
    }
  } catch (_) {
    // The upload check still works without the rubric preview.
  } finally {
    piCheckRubricLoading = false;
  }
}

async function startPiCheck() {
  const asIsFile = piCheckAsIsFileInput?.files?.[0] || null;
  const toBeFile = piCheckToBeFileInput?.files?.[0] || null;
  if (!toBeFile) {
    renderPiCheckError("PI Check 대상 To-Be 문서를 먼저 업로드해 주세요.");
    return;
  }
  if (toBeFile.size > PI_CHECK_MAX_BYTES || (asIsFile && asIsFile.size > PI_CHECK_MAX_BYTES)) {
    renderPiCheckError(`업로드 문서는 파일당 ${formatSize(PI_CHECK_MAX_BYTES)} 이하만 점검할 수 있습니다.`);
    return;
  }
  const invalidFile = [asIsFile, toBeFile].filter(Boolean).find((candidate) => !isSupportedPiCheckFile(candidate));
  if (invalidFile) {
    renderPiCheckError("현재 PI Check는 PPTX, DOCX, PDF, HTML, BPMN, Markdown, Text, JSON 문서 업로드를 지원합니다.");
    return;
  }
  const writerMode = getSelectedWriterMode();
  try {
    const allowed = await ensureWriterModeAccess(writerMode);
    if (!allowed) return;
  } catch (error) {
    renderPiCheckError(error.message || "LLM 사용 인증에 실패했습니다.");
    return;
  }
  piCheckInFlight = true;
  if (piCheckStartButton) {
    piCheckStartButton.disabled = true;
    piCheckStartButton.textContent = "점검 중";
  }
  renderPiCheckStatus({
    label: "PI Check 진행",
    value: asIsFile ? "As-Is / To-Be 비교 중" : "To-Be 문서 분석 중",
    message: "업로드 문서를 PI Check용 JSON으로 정규화하고 PI Agent 체크리스트와 안티패턴 기준으로 점검합니다.",
    status: "loading",
  });
  trackUserEvent("pi_check_started", {
    toBeFileName: toBeFile.name,
    toBeFileSize: toBeFile.size || 0,
    asIsFileName: asIsFile?.name || "",
    asIsFileSize: asIsFile?.size || 0,
  });
  try {
    const totalReadBytes = Math.max(1, (toBeFile.size || 0) + (asIsFile?.size || 0));
    let completedReadBytes = 0;
    const updateReadProgress = (label, fileSize) => (loaded, total) => {
      const currentTotal = Math.max(1, fileSize || total || loaded || 1);
      const currentLoaded = Math.min(currentTotal, loaded || 0);
      const percent = Math.min(45, Math.round(((completedReadBytes + currentLoaded) / totalReadBytes) * 45));
      updatePiCheckProgress("파일 읽기", percent, `${label} 문서를 브라우저에서 읽고 있습니다.`);
    };

    showPiCheckProgress("파일 읽기", 0, "To-Be 문서를 브라우저에서 읽고 있습니다.");
    const toBeContentBase64 = await readFileAsBase64(toBeFile, updateReadProgress("To-Be", toBeFile.size || 0));
    completedReadBytes += toBeFile.size || 0;
    const asIsContentBase64 = asIsFile
      ? await readFileAsBase64(asIsFile, updateReadProgress("As-Is", asIsFile.size || 0))
      : "";
    completedReadBytes += asIsFile?.size || 0;
    updatePiCheckProgress("파일 읽기 완료", 45, "문서를 PI Check 요청 데이터로 준비했습니다.");

    const payload = withClientSession({
      toBe: {
        name: toBeFile.name,
        contentBase64: toBeContentBase64,
      },
      asIs: asIsFile
        ? {
            name: asIsFile.name,
            contentBase64: asIsContentBase64,
          }
        : null,
      writerMode,
      llmAccessToken: writerMode === "llm" ? llmAccessToken : "",
      piCheckMode: writerMode === "llm" ? "hybrid" : "code",
      });
    const response = await postJsonWithUploadProgress(apiPath("/api/pi-check"), payload, (loaded, total) => {
      const ratio = total > 0 ? loaded / total : 0;
      updatePiCheckProgress("파일 업로드", 45 + Math.round(Math.min(1, ratio) * 40), "서버로 문서를 전송하고 있습니다.");
    });
    updatePiCheckProgress("PI 분석", 90, "서버에서 문서를 정규화하고 PI 수준을 점검하고 있습니다.");
    const data = response.data;
    if (!data) {
      throw new Error("서버가 PI Check 결과를 JSON으로 반환하지 못했습니다.");
    }
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "PI Check 중 오류가 발생했습니다.");
    }
    updatePiCheckProgress("PI 분석 완료", 100, "결과를 화면에 표시합니다.");
    renderPiCheckReport(data.report);
    clearPiCheckUploadSelection();
    setMessage(`PI Check 완료: ${data.report.score}점 · ${data.report.judgement} · PI Gate ${piReadinessLabel(data.report.piReadiness || {})}`);
  } catch (error) {
    renderPiCheckError(error.message);
  } finally {
    piCheckInFlight = false;
    if (piCheckStartButton) {
      piCheckStartButton.textContent = "PI Check 시작";
    }
    updatePiCheckFileState();
  }
}

async function exportCurrentPiCheckReport(sourceButton) {
  if (!latestPiCheckReport) {
    setMessage("Export할 PI Check 결과가 없습니다.", true);
    return false;
  }
  if (sourceButton) sourceButton.disabled = true;
  try {
    const response = await fetch(apiPath("/api/pi-check-export"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({ report: latestPiCheckReport })),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok || !data.artifact?.url) {
      throw new Error(data.error || "PI Check 보고서를 export하지 못했습니다.");
    }
    window.open(data.artifact.url, "_blank", "noopener");
    setMessage(`PI Check 보고서를 생성했습니다: ${data.artifact.name}`);
    return true;
  } catch (error) {
    setMessage(error.message || "PI Check 보고서 export 중 오류가 발생했습니다.", true);
    return false;
  } finally {
    if (sourceButton) sourceButton.disabled = !latestPiCheckReport;
  }
}

function isSupportedPiCheckFile(file) {
  const extension = file?.name?.split(".").pop()?.toLowerCase() || "";
  return ["pptx", "docx", "pdf", "html", "htm", "bpmn", "md", "txt", "json"].includes(extension);
}

function showPiCheckProgress(label, percent, detail) {
  if (piCheckProgress) {
    piCheckProgress.hidden = false;
  }
  updatePiCheckProgress(label, percent, detail);
}

function updatePiCheckProgress(label, percent, detail) {
  const safePercent = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
  if (piCheckProgressLabel) {
    piCheckProgressLabel.textContent = label || "업로드 진행 중";
  }
  if (piCheckProgressValue) {
    piCheckProgressValue.textContent = `${safePercent}%`;
  }
  if (piCheckProgressBar) {
    piCheckProgressBar.style.width = `${safePercent}%`;
  }
  if (piCheckProgressDetail) {
    piCheckProgressDetail.textContent = detail || "잠시만 기다려 주세요.";
  }
}

function hidePiCheckProgress() {
  if (piCheckProgress) {
    piCheckProgress.hidden = true;
  }
  updatePiCheckProgress("업로드 준비 중", 0, "파일을 읽고 있습니다.");
}

function postJsonWithUploadProgress(url, payload, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    Object.entries(jsonHeaders()).forEach(([name, value]) => {
      xhr.setRequestHeader(name, value);
    });
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && typeof onProgress === "function") {
        onProgress(event.loaded, event.total);
      }
    };
    xhr.onload = () => {
      const contentType = xhr.getResponseHeader("content-type") || "";
      const responseText = xhr.responseText || "";
      let data = null;
      if (contentType.includes("application/json")) {
        try {
          data = JSON.parse(responseText || "{}");
        } catch (_error) {
          data = null;
        }
      }
      resolve({
        ok: xhr.status >= 200 && xhr.status < 300,
        status: xhr.status,
        data,
      });
    };
    xhr.onerror = () => reject(new Error("업로드 중 네트워크 오류가 발생했습니다."));
    xhr.send(JSON.stringify(payload));
  });
}

function readFileAsBase64(file, onProgress) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onprogress = (event) => {
      if (event.lengthComputable && typeof onProgress === "function") {
        onProgress(event.loaded, event.total);
      }
    };
    reader.onload = () => {
      const result = String(reader.result || "");
      const commaIndex = result.indexOf(",");
      if (typeof onProgress === "function") {
        onProgress(file?.size || 1, file?.size || 1);
      }
      resolve(commaIndex >= 0 ? result.slice(commaIndex + 1) : result);
    };
    reader.onerror = () => reject(new Error("업로드 파일을 읽지 못했습니다."));
    reader.readAsDataURL(file);
  });
}

function clearPiCheckUploadSelection() {
  if (piCheckAsIsFileInput) {
    piCheckAsIsFileInput.value = "";
  }
  if (piCheckToBeFileInput) {
    piCheckToBeFileInput.value = "";
  }
  if (piCheckAsIsFileLabel) {
    piCheckAsIsFileLabel.textContent = "점검 완료 후 As-Is 파일 선택을 정리했습니다.";
  }
  if (piCheckToBeFileLabel) {
    piCheckToBeFileLabel.textContent = "점검 완료 후 To-Be 파일 선택을 정리했습니다.";
  }
  if (piCheckStartButton) {
    piCheckStartButton.disabled = true;
  }
}

function renderPiCheckReport(report) {
  hidePiCheckProgress();
  if (piCheckStats) {
    piCheckStats.hidden = false;
  }
  const safeReport = report || {};
  latestPiCheckReport = safeReport;
  updatePiCheckFooter(safeReport);
  renderPiCheckStatus({
    label: "PI Check 결과",
    value: `${Number(safeReport.score || 0)}점 · ${safeReport.judgement || "-"}`,
    message: safeReport.summary || "PI Check를 완료했습니다.",
    status: piCheckStatusClass(safeReport),
  });
  renderPiCheckStats(safeReport);
  renderPiCheckComparison(safeReport.comparison || null);
  renderPiCheckItems(safeReport.checks || []);
  renderPiCheckAntiPatterns(safeReport.antiPatterns || safeReport.anti_patterns || []);
  renderPiCheckRecommendations((safeReport.actionItems || []).length ? safeReport.actionItems : safeReport.recommendations || []);
}

function renderPiCheckError(messageText) {
  hidePiCheckProgress();
  if (piCheckStats) {
    piCheckStats.hidden = true;
  }
  updatePiCheckFooter(null);
  renderPiCheckStatus({
    label: "PI Check 오류",
    value: "점검 실패",
    message: messageText || "PI Check 중 오류가 발생했습니다.",
    status: "danger",
  });
}

function renderPiCheckStatus({ label, value, message, status }) {
  if (!piCheckStatus) return;
  piCheckStatus.className = `health-check-status-card ${status || ""}`.trim();
  piCheckStatus.innerHTML = "";
  const labelEl = document.createElement("span");
  labelEl.textContent = label || "PI Check";
  const valueEl = document.createElement("strong");
  valueEl.textContent = value || "-";
  const messageEl = document.createElement("p");
  messageEl.innerHTML = lineBreakAfterSentence(message || "");
  piCheckStatus.append(labelEl, valueEl, messageEl);
}

function evaluationModeLabel(value) {
  return value === "hybrid" ? "LLM+코드" : "코드 기반";
}

function renderPiCheckStats(report) {
  if (!piCheckStats) return;
  const readiness = report?.piReadiness || {};
  const gatekeeper = report?.gatekeeper || {};
  const stats = report
    ? [
        { label: "점수", value: `${Number(report.score || 0)} / 100` },
        { label: "판정", value: report.judgement || "-" },
        { label: "PI 제출 Gate", value: piReadinessLabel(readiness) },
        { label: "GateKeeper", value: `${gatekeeper.grade || "-"} · ${gatekeeper.passed ? "통과" : "보완"}` },
        { label: "분석 대상", value: report.asIs ? "As-Is + To-Be" : "To-Be" },
        { label: "평가 방식", value: evaluationModeLabel(report.evaluationMode) },
        { label: "PASS", value: `${Number(report.yesCount ?? report.yes_count ?? 0)}건` },
        { label: "PARTIAL", value: `${Number(report.partialCount ?? report.partial_count ?? 0)}건` },
        { label: "FAIL", value: `${Number(report.noCount ?? report.no_count ?? 0)}건` },
        { label: "보완 항목", value: `${Number(report.actionItemCount ?? report.actionItems?.length ?? 0)}건` },
      ]
    : [
        { label: "점수", value: "-" },
        { label: "판정", value: "-" },
        { label: "평가 방식", value: "코드 기반" },
        { label: "PASS", value: "-" },
        { label: "PARTIAL", value: "-" },
        { label: "FAIL", value: "-" },
      ];
  piCheckStats.innerHTML = "";
  stats.forEach((stat) => {
    const card = document.createElement("article");
    card.className = "health-check-stat-card";
    const label = document.createElement("span");
    label.textContent = stat.label;
    const value = document.createElement("strong");
    value.textContent = stat.value;
    card.append(label, value);
    piCheckStats.appendChild(card);
  });
}

function renderPiCheckComparison(comparison) {
  if (piCheckComparisonSection) {
    piCheckComparisonSection.hidden = !comparison;
  }
  if (!comparison) {
    if (piCheckComparisonBadge) piCheckComparisonBadge.textContent = "비교 대기";
    if (piCheckComparisonList) {
      piCheckComparisonList.className = "pi-check-list empty";
      piCheckComparisonList.textContent = "As-Is 문서를 함께 업로드하면 비교 결과를 표시합니다.";
    }
    return;
  }
  const delta = Number(comparison.deltaScore || 0);
  if (piCheckComparisonBadge) {
    piCheckComparisonBadge.textContent = delta >= 0 ? `+${delta}점` : `${delta}점`;
  }
  if (!piCheckComparisonList) return;
  piCheckComparisonList.innerHTML = "";
  piCheckComparisonList.className = "pi-check-list";
  const summaryItems = [
    {
      title: "PI 수준 변화",
      body: `As-Is ${Number(comparison.asIsScore || 0)}점 → To-Be ${Number(comparison.toBeScore || 0)}점입니다.`,
    },
    {
      title: "개선된 체크 항목",
      body: (comparison.improvedItems || []).length
        ? comparison.improvedItems.map((item) => `${item.id} ${item.from}→${item.to}`).join(", ")
        : "개선으로 판정된 항목이 없습니다.",
    },
    {
      title: "후퇴/주의 항목",
      body: (comparison.regressedItems || []).length
        ? comparison.regressedItems.map((item) => `${item.id} ${item.from}→${item.to}`).join(", ")
        : "후퇴한 항목은 없습니다.",
    },
  ];
  summaryItems.forEach((item) => {
    const card = document.createElement("article");
    card.className = "pi-check-note-card";
    const title = document.createElement("strong");
    title.textContent = item.title;
    const body = document.createElement("p");
    body.textContent = item.body;
    card.append(title, body);
    piCheckComparisonList.appendChild(card);
  });
}

function renderPiCheckItems(items, options = {}) {
  const safeItems = Array.isArray(items) ? items : [];
  const sectionGroups = groupPiCheckItemsBySection(safeItems);
  if (piCheckItemCount) {
    piCheckItemCount.textContent = sectionGroups.length ? `${sectionGroups.length}개 영역 · ${safeItems.length}건` : "0건";
  }
  if (!piCheckItemList) return;
  piCheckItemList.innerHTML = "";
  if (!safeItems.length) {
    piCheckItemList.className = "pi-check-list empty";
    piCheckItemList.textContent = "문서를 업로드하면 검수 영역별 결과를 표시합니다.";
    return;
  }
  piCheckItemList.className = "pi-check-list pi-check-section-list";
  const defaultOpenIndex = options.intro ? 0 : Math.max(0, sectionGroups.findIndex((group) => group.no > 0 || group.partial > 0));
  sectionGroups.forEach((group, index) => {
    const section = document.createElement("details");
    section.className = `pi-check-section-group ${piCheckSectionTone(group)}`;
    section.open = shouldOpenPiCheckSection(index, defaultOpenIndex);

    const summary = document.createElement("summary");
    summary.className = "pi-check-section-summary";
    const head = document.createElement("div");
    head.className = "pi-check-section-title";
    const order = document.createElement("span");
    order.className = "pi-check-section-order";
    order.textContent = String(group.order || index + 1).padStart(2, "0");
    const titleWrap = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = group.name;
    const meta = document.createElement("p");
    meta.textContent = options.intro
      ? `${group.total}개 세부 검수 항목`
      : `PASS ${group.yes} · PARTIAL ${group.partial} · FAIL ${group.no}`;
    titleWrap.append(title, meta);
    head.append(order, titleWrap);

    const stats = document.createElement("div");
    stats.className = "pi-check-section-stats";
    if (options.intro || group.pending === group.total) {
      stats.appendChild(piCheckSectionChip("대기", `${group.total}개`, "pending"));
    } else {
      stats.appendChild(piCheckSectionChip("PASS", group.yes, "success"));
      stats.appendChild(piCheckSectionChip("PARTIAL", group.partial, "warn"));
      stats.appendChild(piCheckSectionChip("FAIL", group.no, "danger"));
    }
    summary.append(head, stats);

    const itemList = document.createElement("div");
    itemList.className = "pi-check-section-items";
    group.items.forEach((item) => itemList.appendChild(renderPiCheckItemCard(item, options)));
    section.append(summary, itemList);
    piCheckItemList.appendChild(section);
  });
}

function renderPiCheckItemCard(item, options = {}) {
  const status = String(item.status || "pending").toLowerCase();
  const card = document.createElement("article");
  card.className = `pi-check-card ${piCheckTone(status)}`;
  const badge = document.createElement("span");
  badge.className = "pi-check-result";
  badge.textContent = piCheckStatusLabel(status);
  const body = document.createElement("div");
  const title = document.createElement("strong");
  const rubricId = item.rubricId || item.rubric_id || item.id || "-";
  title.textContent = `${rubricId} · ${item.question || "PI 체크 항목"}`;
  body.appendChild(title);
  const detailLines = [];
  if (options.intro) {
    if (item.inspectionMethod || item.inspection_method) detailLines.push(`검수 방식: ${item.inspectionMethod || item.inspection_method}`);
    if (item.targetLocation || item.target_location) detailLines.push(`확인 위치: ${item.targetLocation || item.target_location}`);
  } else {
    if (item.inspectionItem || item.inspection_item) detailLines.push(`검수 항목: ${item.inspectionItem || item.inspection_item}`);
    if (item.inspectionMethod || item.inspection_method) detailLines.push(`검수 방식: ${item.inspectionMethod || item.inspection_method}`);
    if (item.statusReason || item.status_reason) detailLines.push(`판정 근거: ${item.statusReason || item.status_reason}`);
    if (Array.isArray(item.evidence) && item.evidence.length) detailLines.push(`근거 신호: ${item.evidence.slice(0, 2).join(" / ")}`);
    if (item.targetLocation || item.target_location) detailLines.push(`보완 위치: ${item.targetLocation || item.target_location}`);
  }
  const suggestionText = item.suggestion || (status === "pending" ? "업로드 후 이 항목을 점검합니다." : "보완 제안이 없습니다.");
  if (!options.intro || !detailLines.length) detailLines.push(`보완 기준: ${suggestionText}`);
  detailLines.forEach((line) => {
    const paragraph = document.createElement("p");
    paragraph.textContent = line;
    body.appendChild(paragraph);
  });
  card.append(badge, body);
  return card;
}

function groupPiCheckItemsBySection(items) {
  const groups = new Map();
  items.forEach((item) => {
    const order = Number(item.sectionOrder || item.section_order || 99);
    const name = item.sectionName || item.section_name || "기타 검수 항목";
    const key = `${String(order).padStart(2, "0")}::${name}`;
    if (!groups.has(key)) {
      groups.set(key, {
        order,
        name,
        items: [],
        total: 0,
        yes: 0,
        partial: 0,
        no: 0,
        pending: 0,
      });
    }
    const group = groups.get(key);
    const status = String(item.status || "pending").toLowerCase();
    group.items.push(item);
    group.total += 1;
    if (status === "yes" || status === "pass") group.yes += 1;
    else if (status === "partial" || status === "warn") group.partial += 1;
    else if (status === "pending") group.pending += 1;
    else group.no += 1;
  });
  return Array.from(groups.values()).sort((a, b) => a.order - b.order || a.name.localeCompare(b.name, "ko"));
}

function piCheckSectionChip(label, value, tone) {
  const chip = document.createElement("span");
  chip.className = `pi-check-section-chip ${tone || ""}`.trim();
  chip.textContent = `${label} ${value}`;
  return chip;
}

function piCheckSectionTone(group) {
  if (group.no > 0) return "danger";
  if (group.partial > 0 || group.pending > 0) return "warn";
  return "success";
}

function shouldOpenPiCheckSection(index, defaultOpenIndex) {
  return index === defaultOpenIndex;
}

function renderPiCheckAntiPatterns(patterns, options = {}) {
  if (piCheckAntiPatternCount) {
    piCheckAntiPatternCount.textContent = `${Array.isArray(patterns) ? patterns.length : 0}건`;
  }
  const emptyText = options.intro ? "PI Check 안티패턴 기준을 불러오고 있습니다." : "감지된 안티패턴이 없습니다.";
  renderPiCheckSimpleList(piCheckAntiPatternList, patterns, emptyText, (item) => ({
    title: `${item.id || "-"} · ${item.name || "안티패턴"}`,
    body: [item.reason || item.rule || "상세 사유가 없습니다.", item.risk ? `주의 리스크: ${item.risk}` : ""].filter(Boolean).join("\n"),
  }));
}

function renderPiCheckRecommendations(recommendations) {
  const items = Array.isArray(recommendations) ? recommendations : [];
  if (piCheckRecommendationCount) {
    piCheckRecommendationCount.textContent = `${items.length}건`;
  }
  renderPiCheckSimpleList(piCheckRecommendationList, items, "PI Check 후 보완 제안을 표시합니다.", (item, index) => ({
    title: typeof item === "object" && item ? `${item.priority || "P3"} · ${item.title || `보완 제안 ${index + 1}`}` : `보완 제안 ${index + 1}`,
    body:
      typeof item === "object" && item
        ? [
            item.targetLocation ? `보완 위치: ${item.targetLocation}` : "",
            item.target ? `보완 위치: ${item.target}` : "",
            item.inspectionMethod ? `검수 방식: ${item.inspectionMethod}` : "",
            item.evidence ? `근거: ${item.evidence}` : "",
            item.suggestion ? `제안: ${item.suggestion}` : "",
          ]
            .filter(Boolean)
            .join("\n")
        : String(item || ""),
  }));
}

function renderPiCheckSimpleList(container, items, emptyText, mapper) {
  if (!container) return;
  container.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    container.className = "pi-check-list empty";
    container.textContent = emptyText;
    return;
  }
  container.className = "pi-check-list";
  items.forEach((item, index) => {
    const mapped = mapper(item, index);
    const card = document.createElement("article");
    card.className = "pi-check-note-card";
    const title = document.createElement("strong");
    title.textContent = mapped.title || `항목 ${index + 1}`;
    const body = document.createElement("p");
    body.textContent = mapped.body || "";
    card.append(title, body);
    container.appendChild(card);
  });
}

function piCheckStatusClass(report) {
  const score = Number(report?.score || 0);
  if (report?.resultBlocked || report?.piReadiness?.status === "fail" || report?.qualityGatePassed === false) return "danger";
  if (report?.piReadinessGatePassed === false) return "warn";
  if (score >= 85 && Number(report?.noCount ?? report?.no_count ?? 0) === 0) return "success";
  if (score >= 70) return "warn";
  return "danger";
}

function piReadinessLabel(readiness) {
  const status = String(readiness?.status || "").toLowerCase();
  if (status === "pass") return "통과";
  if (status === "warn") return "보완";
  if (status === "fail") return "미통과";
  return "-";
}

function updatePiCheckFooter(report) {
  if (piCheckFooter) {
    piCheckFooter.hidden = !report;
  }
  if (piCheckExportButton) {
    piCheckExportButton.disabled = !report;
  }
  if (piCheckFooterSummary) {
    const gatekeeper = report?.gatekeeper || {};
    const readiness = report?.piReadiness || {};
    const checkItems = Array.isArray(report?.checks) ? report.checks : [];
    const sectionCount = report ? groupPiCheckItemsBySection(checkItems).length : 0;
    piCheckFooterSummary.textContent = report
      ? `검수 영역 ${sectionCount}개, 세부 항목 ${checkItems.length}건, GateKeeper ${gatekeeper.grade || "-"} 등급, PI 제출 Gate ${piReadinessLabel(readiness)} 결과를 보고서로 내보낼 수 있습니다.`
      : "PI Check 결과의 검수 영역, 세부 방식, GateKeeper 판단을 보고서로 내보낼 수 있습니다.";
  }
}

function piCheckTone(status) {
  if (status === "yes" || status === "pass") return "success";
  if (status === "partial" || status === "warn" || status === "pending") return "warn";
  return "danger";
}

function piCheckStatusLabel(status) {
  if (status === "yes" || status === "pass") return "PASS";
  if (status === "partial" || status === "warn") return "PARTIAL";
  if (status === "pending") return "CHECK";
  return "FAIL";
}

function openHealthCheckModal() {
  if (healthCheckModal) {
    healthCheckModal.hidden = false;
  }
  if (healthCheckInFlight) {
    renderHealthCheckLoading();
    return;
  }
  const cachedReport = cachedHealthCheckReport();
  if (cachedReport) {
    renderHealthCheckReport(cachedReport);
    return;
  }
  renderHealthCheckIntro();
}

function closeHealthCheckModal() {
  if (healthCheckModal) {
    healthCheckModal.hidden = true;
  }
}

async function startHealthCheck() {
  const targetPayload = healthCheckTargetPayload();
  if (!targetPayload) {
    renderHealthCheckError("Health Check 대상 문서를 먼저 선택해 주세요.");
    return;
  }
  const writerMode = getSelectedWriterMode();
  let payload;
  try {
    const allowed = await ensureWriterModeAccess(writerMode);
    if (!allowed) return;
    payload = withClientSession({
      ...targetPayload,
      writerMode,
      llmAccessToken: writerMode === "llm" ? llmAccessToken : "",
      healthCheckMode: writerMode === "llm" ? "hybrid" : "code",
      healthCheckUseLlm: writerMode === "llm",
    });
  } catch (error) {
    renderHealthCheckError(error.message || "LLM 사용 인증에 실패했습니다.");
    return;
  }
  healthCheckInFlight = true;
  renderHealthCheckLoading();
  trackUserEvent("health_check_started", {
    selectedName,
    draftId: selectedDraft?.id || "",
    healthCheckMode: writerMode === "llm" ? "hybrid" : "code",
  });
  if (healthCheckButton) healthCheckButton.disabled = true;
  if (healthCheckStartButton) healthCheckStartButton.disabled = true;
  try {
    const response = await fetch(apiPath("/api/policies/health-check"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(payload),
    });
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json().catch(() => ({})) : null;
    if (!data) {
      throw new Error("서버가 Health Check 결과를 JSON으로 반환하지 못했습니다. Render 배포 또는 재시작 중일 수 있으니 잠시 후 다시 시도해 주세요.");
    }
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "Health Check 중 오류가 발생했습니다.");
    }
    const cacheKey = healthCheckCacheKey();
    if (cacheKey) {
      healthCheckReportsByPolicy.set(cacheKey, data.report);
    }
    renderHealthCheckReport(data.report);
    setMessage(`Health Check 완료: ${data.report.score}점 · ${data.report.judgement}`);
  } catch (error) {
    renderHealthCheckError(error.message);
  } finally {
    healthCheckInFlight = false;
    if (healthCheckButton) healthCheckButton.disabled = false;
    if (healthCheckStartButton) healthCheckStartButton.disabled = false;
  }
}

function healthCheckTargetPayload() {
  return selectedName
    ? { name: selectedName }
    : selectedDraft?.resumeFrom
      ? { draftResumeFrom: selectedDraft.resumeFrom, draftId: selectedDraft.id || "" }
      : null;
}

function renderHealthCheckIntro() {
  latestHealthCheckReport = null;
  setHealthCheckDisplayMode("intro");
  const hasTarget = Boolean(healthCheckCacheKey());
  if (healthCheckSummary) {
    healthCheckSummary.textContent = "문서 설계 품질 점검표 기준으로 현재 문서의 구조, 정책 구체성, 예외 대응, 추적성을 평가합니다. 실행 전에도 영역별 체크 항목을 먼저 확인할 수 있습니다.";
  }
  if (healthCheckStartButton) {
    healthCheckStartButton.disabled = false;
    healthCheckStartButton.textContent = "Health Check 시작";
  }
  renderHealthCheckStatus({
    label: "점검 기준",
    value: "문서 품질 점검",
    message: hasTarget
      ? "10개 영역, 50개 체크 항목과 필수 게이트 G1~G7을 기준으로 평가합니다."
      : "문서 작업실에서 정책서를 선택한 뒤 실행할 수 있습니다.",
    status: hasTarget ? "info" : "warn",
  });
  renderHealthCheckStats(null);
  if (healthCheckRubric?.sections?.length) {
    renderHealthCheckSections(healthCheckRubric.sections);
  } else {
    renderHealthCheckSections([]);
    loadHealthCheckRubric();
  }
  renderHealthCheckGates([]);
  renderHealthCheckItems([]);
}

function setHealthCheckDisplayMode(mode) {
  const isResult = mode === "result";
  const isIntro = mode === "intro";
  const isLoading = mode === "loading";
  const modal = healthCheckModal?.querySelector(".health-check-modal");
  if (modal) {
    modal.dataset.mode = mode || "";
  }
  const sectionWrap = healthCheckSectionList?.closest(".health-check-section");
  const sectionTitle = sectionWrap?.querySelector(".health-check-section-head strong");
  if (healthCheckStats) {
    healthCheckStats.hidden = !isResult;
  }
  if (sectionWrap) {
    sectionWrap.hidden = !(isResult || isIntro || isLoading);
  }
  if (sectionTitle) {
    sectionTitle.textContent = isIntro ? "체크 항목" : isLoading ? "점검 진행" : "영역별 결과";
  }
  const gateWrap = healthCheckGateList?.closest(".health-check-section");
  if (gateWrap) {
    gateWrap.hidden = !(isResult || isLoading);
  }
  const itemWrap = healthCheckItemList?.closest(".health-check-section");
  if (itemWrap) {
    itemWrap.hidden = !(isResult || isLoading);
  }
  if (healthCheckFooter) {
    healthCheckFooter.hidden = !isResult;
  }
  if (!isResult) {
    updateHealthCheckRevisionState();
  }
}

async function loadHealthCheckRubric() {
  if (healthCheckRubricLoading || healthCheckRubric?.sections?.length) return;
  healthCheckRubricLoading = true;
  if (healthCheckSectionList) {
    healthCheckSectionList.className = "health-check-section-list empty";
    healthCheckSectionList.textContent = "Health Check 체크 항목을 불러오고 있습니다.";
  }
  try {
    const response = await fetch(apiPath("/api/policies/health-check-rubric"), {
      method: "GET",
      headers: jsonHeaders(),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok || !data.rubric) {
      throw new Error(data.error || "Health Check 체크 항목을 불러오지 못했습니다.");
    }
    healthCheckRubric = data.rubric;
    if (!healthCheckInFlight && !latestHealthCheckReport && !healthCheckModal?.hidden) {
      renderHealthCheckSections(healthCheckRubric.sections || []);
    }
  } catch (error) {
    if (healthCheckSectionList && !healthCheckInFlight && !latestHealthCheckReport) {
      healthCheckSectionList.className = "health-check-section-list empty";
      healthCheckSectionList.textContent = error.message || "Health Check 체크 항목을 불러오지 못했습니다.";
    }
  } finally {
    healthCheckRubricLoading = false;
  }
}

function renderHealthCheckLoading(options = {}) {
  latestHealthCheckReport = null;
  setHealthCheckDisplayMode("loading");
  const recheckItemCount = Number(options.recheckItemCount || 0);
  if (healthCheckSummary) {
    healthCheckSummary.textContent = recheckItemCount
      ? `선택한 FAIL 항목 ${recheckItemCount}건을 다시 읽고, 기존 Health Check 결과와 비교하고 있습니다.`
      : "정책서 설계 품질 점검표 기준으로 문서를 읽고 있습니다. 진행 중에도 점검 단계와 영역별 확인 흐름을 볼 수 있습니다.";
  }
  if (healthCheckStartButton) {
    healthCheckStartButton.disabled = true;
    healthCheckStartButton.textContent = "점검 중";
  }
  renderHealthCheckStatus({
    label: "점검 중",
    value: "처리 중",
    message: "정책 범위, CX, 프로세스, 구조 연결, 상태, 정책 구체성, 예외 대응, BSS, 데이터, 추적성을 확인합니다.",
    status: "loading",
  });
  renderHealthCheckStats(null);
  renderHealthCheckProgress(options);
}

function renderHealthCheckError(messageText) {
  latestHealthCheckReport = null;
  setHealthCheckDisplayMode("error");
  if (healthCheckSummary) {
    healthCheckSummary.textContent = "Health Check를 완료하지 못했습니다.";
  }
  if (healthCheckStartButton) {
    healthCheckStartButton.disabled = false;
    healthCheckStartButton.textContent = cachedHealthCheckReport() ? "재점검" : "Health Check 시작";
  }
  renderHealthCheckStatus({
    label: "점검 실패",
    value: "오류",
    message: messageText || "Health Check 중 오류가 발생했습니다.",
    status: "danger",
  });
  renderHealthCheckStats(null);
  renderHealthCheckSections([]);
  renderHealthCheckGates([]);
  renderHealthCheckItems([]);
}

function renderHealthCheckReport(report) {
  const safeReport = report || {};
  latestHealthCheckReport = safeReport;
  setHealthCheckDisplayMode("result");
  const cacheKey = healthCheckCacheKey();
  if (cacheKey) {
    healthCheckReportsByPolicy.set(cacheKey, safeReport);
  }
  if (healthCheckSummary) {
    healthCheckSummary.textContent = "Health Check 결과를 확인하고 낮은 영역과 필수 게이트 미통과 항목을 보완할 수 있습니다.";
  }
  if (healthCheckStartButton) {
    healthCheckStartButton.disabled = false;
    healthCheckStartButton.textContent = "재점검";
  }
  renderHealthCheckStatus({
    label: "검토 결과",
    value: `${Number(safeReport.score || 0)}점 · ${safeReport.judgement || "-"}`,
    message: safeReport.summary || "Health Check를 완료했습니다.",
    status: healthCheckStatusClass(safeReport),
  });
  renderHealthCheckStats(safeReport);
  renderHealthCheckSections(safeReport.sections || []);
  renderHealthCheckGates(healthCheckGatesWithGatekeeper(safeReport));
  renderHealthCheckItems(safeReport.actionItems || [], safeReport);
  updateHealthCheckRevisionState();
}

function renderHealthCheckStatus({ label, value, message, status }) {
  if (!healthCheckStatus) return;
  healthCheckStatus.className = `health-check-status-card ${status || ""}`.trim();
  healthCheckStatus.innerHTML = "";
  const labelEl = document.createElement("span");
  labelEl.textContent = label || "점검 상태";
  const valueEl = document.createElement("strong");
  valueEl.textContent = value || "-";
  const messageEl = document.createElement("p");
  messageEl.innerHTML = lineBreakAfterSentence(message || "");
  healthCheckStatus.append(labelEl, valueEl, messageEl);
}

function renderHealthCheckStats(report) {
  if (!healthCheckStats) return;
  const stats = report
    ? [
        { label: "총점", value: `${Number(report.score || 0)} / ${Number(report.maxScore || 100)}` },
        { label: "판정", value: report.judgement || "-" },
        { label: "필수 게이트", value: report.mandatoryGatePassed ? "통과" : "보완 필요" },
        { label: "평가 품질", value: healthCheckGatekeeperLabel(report.gatekeeper) },
        { label: "산출물 동기화", value: healthCheckArtifactDriftLabel(report.artifactDrift) },
        { label: "버전 추이", value: healthCheckTrendLabel(report.versionTrend) },
        { label: "평가 방식", value: evaluationModeLabel(report.evaluationMode) },
        { label: "검증 범위", value: report.templateProfile?.label || (report.templateType === "full" ? "Full 버전" : "간소화 버전") },
        { label: "마지막 실행", value: formatDate(report.checkedAt || report.created_at || "") },
      ]
    : [
        { label: "총점", value: "-" },
        { label: "판정", value: "-" },
        { label: "필수 게이트", value: "-" },
        { label: "평가 품질", value: "-" },
        { label: "산출물 동기화", value: "-" },
        { label: "버전 추이", value: "-" },
        { label: "평가 방식", value: "코드 기반" },
        { label: "검증 범위", value: "-" },
      ];
  healthCheckStats.innerHTML = "";
  stats.forEach((stat) => {
    const card = document.createElement("article");
    card.className = "health-check-stat-card";
    const label = document.createElement("span");
    label.textContent = stat.label;
    const value = document.createElement("strong");
    value.textContent = stat.value;
    card.append(label, value);
    healthCheckStats.appendChild(card);
  });
}

function renderHealthCheckSections(sections) {
  if (healthCheckSectionCount) {
    healthCheckSectionCount.textContent = `${Array.isArray(sections) ? sections.length : 0}개 영역`;
  }
  renderHealthCheckSectionChart(sections);
  if (!healthCheckSectionList) return;
  healthCheckSectionList.innerHTML = "";
  if (!Array.isArray(sections) || sections.length === 0) {
    healthCheckSectionList.className = "health-check-section-list empty";
    healthCheckSectionList.textContent = "Health Check 결과를 기다리고 있습니다.";
    return;
  }
  healthCheckSectionList.className = "health-check-section-list";
  sections.forEach((section) => {
    const isEvaluated = Object.prototype.hasOwnProperty.call(section, "score");
    const sectionMaxScore = Number(section.maxScore ?? section.max_score ?? 10);
    const card = document.createElement("article");
    card.className = `health-check-section-card ${isEvaluated ? healthCheckSectionTone(section.score) : "pending"}`;
    const header = document.createElement("div");
    header.className = "health-check-section-card-head";
    const titleWrap = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = section.name || "점검 영역";
    const gap = document.createElement("p");
    gap.textContent = isEvaluated
      ? section.majorGap || "주요 보완점이 없습니다."
      : "이 영역에서 확인할 체크 항목입니다.";
    titleWrap.append(title, gap);
    header.appendChild(titleWrap);
    if (isEvaluated) {
      const score = document.createElement("span");
      score.textContent = `${Number(section.score || 0)} / ${sectionMaxScore}`;
      header.appendChild(score);
    }
    card.appendChild(header);

    const items = Array.isArray(section.items) ? section.items : [];
    if (items.length > 0) {
      const detailList = document.createElement("div");
      detailList.className = "health-check-section-detail-list";
      items.forEach((item) => {
        const itemEvaluated = Object.prototype.hasOwnProperty.call(item, "score");
        const row = document.createElement("div");
        row.className = `health-check-section-detail-row ${itemEvaluated ? healthCheckSectionItemTone(item.score) : "pending"}`;
        const rowTop = document.createElement("div");
        rowTop.className = "health-check-section-detail-top";
        const question = document.createElement("strong");
        question.textContent = `${item.id || "-"} · ${item.question || "체크 항목"}`;
        rowTop.appendChild(question);
        if (itemEvaluated) {
          const itemMaxScore = Number(item.maxScore ?? item.max_score ?? 2);
          const itemScore = Number(item.score || 0);
          const itemPassed = itemScore >= itemMaxScore;
          const resultBadge = document.createElement(itemPassed ? "span" : "button");
          resultBadge.className = `health-check-result-badge ${itemPassed ? "pass" : "fail"}`;
          resultBadge.textContent = itemPassed ? "PASS" : "FAIL";
          rowTop.appendChild(resultBadge);
          if (!itemPassed) {
            const selectWrap = document.createElement("label");
            selectWrap.className = "health-check-select-wrap";
            const selectInput = document.createElement("input");
            selectInput.type = "checkbox";
            selectInput.className = "health-check-select";
            selectInput.dataset.sectionId = section.id || "";
            selectInput.dataset.itemId = item.id || "";
            selectInput.disabled = !canCurrentUserWritePolicies() || !selectedName || selectedPolicyCompleted();
            selectWrap.title = !selectedName
              ? "작성 중단 초안은 먼저 문서로 저장한 뒤 자동 보완할 수 있습니다."
              : !canCurrentUserWritePolicies()
                ? "조회 권한은 자동 보완을 실행할 수 없습니다."
              : selectedPolicyCompleted()
                ? "작성 완료 상태에서는 완료 취소 후 자동 보완할 수 있습니다."
                : "일괄 자동 보완에 포함합니다.";
            const selectText = document.createElement("span");
            selectText.textContent = "보완";
            selectWrap.append(selectInput, selectText);
            rowTop.appendChild(selectWrap);
            resultBadge.type = "button";
            resultBadge.setAttribute("aria-expanded", "false");
            const detailPanel = document.createElement("div");
            detailPanel.className = "health-check-section-detail-extra";
            detailPanel.hidden = true;
            const evidence = document.createElement("p");
            evidence.textContent = `판단 근거: ${item.evidence || "확인된 근거가 없습니다."}`;
            const suggestion = document.createElement("p");
            suggestion.textContent = `보완 제안: ${item.suggestion || "추가 보완 제안이 없습니다."}`;
            const location = document.createElement("p");
            location.textContent = `관련 위치: ${item.relatedLocation || "문서 본문"}`;
            const noteField = document.createElement("label");
            noteField.className = "health-check-note-field";
            const noteCaption = document.createElement("span");
            noteCaption.textContent = "수정 방향 메모(선택)";
            const noteInput = document.createElement("textarea");
            noteInput.className = "health-check-auto-note";
            noteInput.rows = 2;
            noteInput.placeholder = "예: 정책 상세에 예외 조건과 이력 기준을 추가해줘.";
            noteInput.dataset.sectionId = section.id || "";
            noteInput.dataset.itemId = item.id || "";
            noteField.append(noteCaption, noteInput);
            detailPanel.append(evidence, suggestion, location, noteField);
            resultBadge.addEventListener("click", () => {
              const expanded = resultBadge.getAttribute("aria-expanded") === "true";
              setHealthCheckDetailExpanded(row, !expanded);
            });
            row.appendChild(rowTop);
            row.appendChild(detailPanel);
            detailList.appendChild(row);
            return;
          }
        }
        row.appendChild(rowTop);
        detailList.appendChild(row);
      });
      card.appendChild(detailList);
    }
    healthCheckSectionList.appendChild(card);
  });
}

function healthCheckProgressAreas() {
  const rubricSections = Array.isArray(healthCheckRubric?.sections) ? healthCheckRubric.sections : [];
  const source = rubricSections.length
    ? rubricSections.map((section) => section?.name || "점검 영역")
    : HEALTH_CHECK_FALLBACK_AREAS;
  return source.slice(0, 10).map((name, index) => ({
    name,
    target: 46 + ((index * 9) % 44),
    status: index < 3 ? "읽는 중" : index < 7 ? "대기" : "후속 확인",
  }));
}

function renderHealthCheckProgress(options = {}) {
  const recheckItemCount = Number(options.recheckItemCount || 0);
  const areas = healthCheckProgressAreas();
  if (healthCheckSectionCount) {
    healthCheckSectionCount.textContent = `${areas.length}개 영역 점검 중`;
  }
  if (healthCheckSectionChart) {
    healthCheckSectionChart.hidden = false;
    healthCheckSectionChart.className = "health-check-section-chart health-check-progress-chart";
    healthCheckSectionChart.innerHTML = "";
    const hero = document.createElement("div");
    hero.className = "health-check-progress-hero";
    const heroText = document.createElement("div");
    const heroTitle = document.createElement("strong");
    heroTitle.textContent = recheckItemCount ? "선택 항목 재점검 진행 중" : "Health Check 진행 중";
    const heroDetail = document.createElement("p");
    heroDetail.textContent = recheckItemCount
      ? `선택한 FAIL 항목 ${recheckItemCount}건을 기존 결과와 대조하고 있습니다.`
      : "점검이 끝날 때까지 현재 레이아웃을 유지하면서 영역별 확인 흐름을 표시합니다.";
    heroText.append(heroTitle, heroDetail);
    const heroBadge = document.createElement("span");
    heroBadge.textContent = "RUNNING";
    hero.append(heroText, heroBadge);
    const track = document.createElement("div");
    track.className = "health-check-progress-track";
    const fill = document.createElement("span");
    track.appendChild(fill);
    const barList = document.createElement("div");
    barList.className = "health-check-progress-bars";
    areas.forEach((area, index) => {
      const row = document.createElement("div");
      row.className = "health-check-progress-area-row";
      row.style.setProperty("--target", `${area.target}%`);
      row.style.setProperty("--delay", `${index * 0.11}s`);
      const label = document.createElement("span");
      label.textContent = area.name;
      const bar = document.createElement("i");
      bar.setAttribute("aria-hidden", "true");
      const state = document.createElement("strong");
      state.textContent = area.status;
      row.append(label, bar, state);
      barList.appendChild(row);
    });
    healthCheckSectionChart.append(hero, track, barList);
  }
  if (healthCheckSectionList) {
    healthCheckSectionList.innerHTML = "";
    healthCheckSectionList.className = "health-check-progress-step-list";
    HEALTH_CHECK_PROGRESS_STEPS.forEach((step, index) => {
      const card = document.createElement("article");
      card.className = `health-check-progress-step-card ${index === 1 ? "active" : index === 0 ? "done" : ""}`;
      const marker = document.createElement("span");
      marker.textContent = step.label;
      const body = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = step.title;
      const detail = document.createElement("p");
      detail.textContent = step.description;
      body.append(title, detail);
      card.append(marker, body);
      healthCheckSectionList.appendChild(card);
    });
  }
  if (healthCheckGateCount) {
    healthCheckGateCount.textContent = "진행 중";
  }
  if (healthCheckGateList) {
    healthCheckGateList.innerHTML = "";
    healthCheckGateList.className = "health-check-gate-list health-check-progress-gate-list";
    [
      ["Gate G1~G7", "요구사항 커버리지, 구조 연결성, 정책 상세화 Gate를 확인합니다."],
      ["GateKeeper", "평가 결과가 실제 문서 근거와 맞는지 오탐 가능성을 함께 확인합니다."],
      ["산출물 동기화", "HTML, JSON spec, BPMN, trace 산출물이 같은 기준을 가리키는지 확인합니다."],
    ].forEach(([titleText, detailText], index) => {
      const card = document.createElement("article");
      card.className = `health-check-progress-gate-card ${index === 0 ? "active" : ""}`;
      const marker = document.createElement("span");
      marker.textContent = index === 0 ? "CHECK" : "QUEUE";
      const title = document.createElement("strong");
      title.textContent = titleText;
      const detail = document.createElement("p");
      detail.textContent = detailText;
      card.append(marker, title, detail);
      healthCheckGateList.appendChild(card);
    });
  }
  if (healthCheckItemCount) {
    healthCheckItemCount.textContent = recheckItemCount ? `${recheckItemCount}건 재점검` : "집계 중";
  }
  if (healthCheckItemList) {
    healthCheckItemList.innerHTML = "";
    healthCheckItemList.className = "health-check-item-list health-check-progress-item-list";
    [
      ["보완 후보 수집", "점수가 낮거나 Gate에 걸린 항목을 수정 위치와 함께 모읍니다."],
      ["우선순위 분류", "Critical/Major 성격의 항목을 먼저 보이도록 정렬합니다."],
    ].forEach(([titleText, detailText]) => {
      const card = document.createElement("article");
      card.className = "health-check-item-card p3 health-check-progress-card";
      const top = document.createElement("div");
      top.className = "health-check-item-top";
      const title = document.createElement("strong");
      title.textContent = titleText;
      const badge = document.createElement("span");
      badge.textContent = "대기";
      top.append(title, badge);
      const detail = document.createElement("p");
      detail.textContent = detailText;
      card.append(top, detail);
      healthCheckItemList.appendChild(card);
    });
  }
}

function setHealthCheckDetailExpanded(row, expanded) {
  if (!row) return;
  const resultBadge = row.querySelector(".health-check-result-badge.fail");
  const detailPanel = row.querySelector(".health-check-section-detail-extra");
  if (!resultBadge || !detailPanel) return;
  resultBadge.setAttribute("aria-expanded", expanded ? "true" : "false");
  detailPanel.hidden = !expanded;
  row.classList.toggle("open", expanded);
}

async function startSelectedHealthCheckRevision(sourceButton) {
  if (!guardWritePermission("조회 권한은 Health Check 자동 보완을 실행할 수 없습니다.")) return false;
  if (!selectedName) {
    setMessage("작성 중단 초안은 먼저 문서로 저장한 뒤 자동 보완할 수 있습니다.", true);
    return false;
  }
  if (selectedPolicyCompleted()) {
    setMessage("작성 완료 상태에서는 '작성 완료 취소' 후에만 Health Check 자동 보완을 할 수 있습니다.", true);
    return false;
  }
  const selectedItems = selectedHealthCheckRevisionItems();
  if (selectedItems.length === 0) {
    setMessage("자동 보완할 FAIL 항목을 하나 이상 선택해 주세요.", true);
    return false;
  }
  const hasMetaBlocker = Boolean(latestHealthCheckReport?.resultBlocked);
  const instruction = buildHealthCheckRevisionInstruction(selectedItems);
  trackUserEvent("health_check_auto_revision_requested", {
    selectedName,
    itemCount: selectedItems.length,
    itemIds: selectedItems.map((entry) => entry.item?.id || "").filter(Boolean).slice(0, 20),
    resultBlocked: hasMetaBlocker,
  });
  if (hasMetaBlocker) {
    setMessage("GateKeeper 또는 산출물 동기화 경고가 있지만, 선택한 FAIL 항목 보완은 진행합니다. 보완 후 전체 Health Check를 다시 실행해 주세요.");
  }
  const started = await startRevisionRequest(instruction, null, sourceButton);
  if (started) {
    closeHealthCheckModal();
  }
  return started;
}

async function startSelectedHealthCheckRecheck(sourceButton) {
  const targetPayload = healthCheckTargetPayload();
  if (!targetPayload) {
    renderHealthCheckError("Health Check 대상 문서를 먼저 선택해 주세요.");
    return false;
  }
  if (!latestHealthCheckReport) {
    setMessage("먼저 Health Check를 실행한 뒤 실패 항목만 재점검할 수 있습니다.", true);
    return false;
  }
  const hasMetaBlocker = Boolean(latestHealthCheckReport.resultBlocked);
  const selectedIds = selectedHealthCheckRevisionItems().map((entry) => entry.item?.id).filter(Boolean);
  const itemIds = selectedIds.length ? selectedIds : failedHealthCheckItemIds();
  if (!itemIds.length) {
    setMessage("재점검할 FAIL 항목이 없습니다.");
    return false;
  }
  if (hasMetaBlocker) {
    setMessage("평가 품질 또는 산출물 동기화 경고가 있지만, 선택 항목 재점검은 진행합니다. 필요하면 전체 Health Check도 다시 실행해 주세요.");
  }
  const writerMode = getSelectedWriterMode();
  let payload;
  try {
    const allowed = await ensureWriterModeAccess(writerMode);
    if (!allowed) return false;
    payload = withClientSession({
      ...targetPayload,
      writerMode,
      llmAccessToken: writerMode === "llm" ? llmAccessToken : "",
      healthCheckMode: writerMode === "llm" ? "hybrid" : "code",
      healthCheckUseLlm: writerMode === "llm",
      recheckItemIds: itemIds,
      previousReport: latestHealthCheckReport,
    });
  } catch (error) {
    renderHealthCheckError(error.message || "LLM 사용 인증에 실패했습니다.");
    return false;
  }
  if (sourceButton) sourceButton.disabled = true;
  healthCheckInFlight = true;
  renderHealthCheckLoading({ recheckItemCount: itemIds.length });
  try {
    const response = await fetch(apiPath("/api/policies/health-check"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "선택 항목 재점검 중 오류가 발생했습니다.");
    }
    renderHealthCheckReport(data.report);
    setMessage(`선택 항목 재점검 완료: ${itemIds.length}건 · ${data.report.score}점`);
    return true;
  } catch (error) {
    renderHealthCheckError(error.message);
    return false;
  } finally {
    healthCheckInFlight = false;
    if (sourceButton) sourceButton.disabled = false;
  }
}

function healthCheckHasArtifactSyncIssue(report) {
  const drift = report?.artifactDrift;
  const driftStatus = drift && typeof drift === "object" ? String(drift.status || "").toLowerCase() : "";
  if (healthCheckNeedsHtmlSpecSync(report)) return true;
  if (driftStatus === "fail" || driftStatus === "warn") return true;
  const artifactPlan = report?.remediationPlan?.artifactSync;
  return Array.isArray(artifactPlan) && artifactPlan.length > 0;
}

function healthCheckNeedsHtmlSpecSync(report) {
  const drift = report?.artifactDrift;
  if (!drift || typeof drift !== "object") return false;
  if (drift.htmlSpecSyncNeeded) return true;
  return Array.isArray(drift.issues) && drift.issues.some((issue) => issue?.id === "DRIFT-HTML-RUNTIME-SOURCE");
}

async function startHealthCheckArtifactSyncRepair(sourceButton) {
  if (!guardWritePermission("조회 권한은 산출물 동기화 복구를 실행할 수 없습니다.")) return false;
  if (!selectedName) {
    setMessage("산출물 동기화 복구 대상 정책서를 먼저 선택해 주세요.", true);
    return false;
  }
  if (selectedPolicyCompleted()) {
    setMessage("작성 완료 상태에서는 '작성 완료 취소' 후에만 산출물 동기화 복구를 실행할 수 있습니다.", true);
    return false;
  }
  if (!healthCheckHasArtifactSyncIssue(latestHealthCheckReport)) {
    setMessage("복구할 산출물 동기화 이슈가 없습니다.");
    return false;
  }
  const htmlSpecSync = healthCheckNeedsHtmlSpecSync(latestHealthCheckReport);
  const originalText = sourceButton?.textContent || "";
  if (sourceButton) {
    sourceButton.disabled = true;
    sourceButton.textContent = htmlSpecSync ? "보정 중" : "복구 중";
  }
  setMessage(
    htmlSpecSync
      ? "사용자가 저장한 HTML을 기준으로 spec 메타와 보조 산출물을 보정하고 있습니다."
      : "HTML, spec, BPMN, Trace 산출물을 현재 정책서 기준으로 다시 맞추고 있습니다."
  );
  trackUserEvent("health_check_artifact_sync_repair_requested", {
    selectedName,
    driftStatus: latestHealthCheckReport?.artifactDrift?.status || "",
    htmlSpecSync,
  });
  try {
    const response = await fetch(apiPath(htmlSpecSync ? "/api/policies/html-spec-sync" : "/api/policies/artifact-sync-repair"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(
        withClientSession({
          name: selectedName,
          author: currentUser?.name || currentUser?.employeeId || "Policy Web",
        }),
      ),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "산출물 동기화 복구 중 오류가 발생했습니다.");
    }
    setMessage(data.summary || (htmlSpecSync ? "HTML 기준 spec 보정을 완료했습니다. Health Check를 다시 실행합니다." : "산출물 동기화 복구를 완료했습니다. Health Check를 다시 실행합니다."));
    await loadPolicies(data.name || selectedName, { autoSelect: true });
    await startHealthCheck();
    return true;
  } catch (error) {
    setMessage(error.message || "산출물 동기화 복구 중 오류가 발생했습니다.", true);
    return false;
  } finally {
    if (sourceButton) {
      sourceButton.textContent = originalText || "산출물 동기화 복구";
    }
    updateHealthCheckRevisionState();
  }
}

async function exportCurrentHealthCheckReport(sourceButton) {
  const targetPayload = healthCheckTargetPayload();
  if (!targetPayload || !latestHealthCheckReport) {
    setMessage("Export할 Health Check 결과가 없습니다.", true);
    return false;
  }
  if (sourceButton) sourceButton.disabled = true;
  try {
    const response = await fetch(apiPath("/api/policies/health-check-export"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession({ ...targetPayload, report: latestHealthCheckReport })),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok || !data.artifact?.url) {
      throw new Error(data.error || "Health Check 보고서를 export하지 못했습니다.");
    }
    window.open(data.artifact.url, "_blank", "noopener");
    setMessage(`Health Check 보고서를 생성했습니다: ${data.artifact.name}`);
    return true;
  } catch (error) {
    setMessage(error.message || "Health Check 보고서 export 중 오류가 발생했습니다.", true);
    return false;
  } finally {
    if (sourceButton) sourceButton.disabled = false;
  }
}

function devFormatTargetPayload() {
  const item = selectedPolicyItem();
  if (!item) return null;
  if (item.templateType !== "full") return null;
  return { name: item.name };
}

function openDevFormatExportModal() {
  if (devFormatExportModal) {
    devFormatExportModal.hidden = false;
  }
  if (devFormatExportInFlight) {
    renderDevFormatExportLoading();
  } else if (latestDevFormatExport) {
    renderDevFormatExportResult(latestDevFormatExport);
  } else {
    renderDevFormatExportIntro();
  }
}

function closeDevFormatExportModal() {
  if (devFormatExportModal) {
    devFormatExportModal.hidden = true;
  }
}

function renderDevFormatExportIntro() {
  if (devFormatExportSummary) {
    devFormatExportSummary.textContent = "Full 정책서를 디자인/개발팀 AI input용 산출물로 변환합니다.";
  }
  if (devFormatExportStartButton) {
    devFormatExportStartButton.disabled = !devFormatTargetPayload();
    devFormatExportStartButton.textContent = "Export 실행";
  }
  renderDevFormatExportStatus({
    label: "Export 준비",
    value: devFormatTargetPayload() ? "실행 가능" : "Full 문서 필요",
    message: devFormatTargetPayload()
      ? "선택한 Full 정책서를 User Case별 Markdown, mapping.csv, entities.yaml, warnings.md가 포함된 ZIP으로 변환합니다."
      : "AI Input Export는 Full 버전 정책서에서만 실행할 수 있습니다.",
    status: devFormatTargetPayload() ? "success" : "warn",
  });
  renderDevFormatExportStats(null);
  renderDevFormatExportArtifacts(null);
  renderDevFormatExportWarnings(null);
  renderDevFormatExportDiagramNotes(null);
  updateDevFormatExportFooter(null);
}

function renderDevFormatExportLoading() {
  if (devFormatExportSummary) {
    devFormatExportSummary.textContent = "정책서 구조를 읽고 ZIP 파일을 생성하고 있습니다.";
  }
  if (devFormatExportStartButton) {
    devFormatExportStartButton.disabled = true;
    devFormatExportStartButton.textContent = "Export 중";
  }
  renderDevFormatExportStatus({
    label: "Export 중",
    value: "처리 중",
    message: "Full 정책서를 파싱하고 User Case별 문서, ID 매핑, 검증 리포트, ZIP 파일을 생성합니다.",
    status: "loading",
  });
  renderDevFormatExportStats(null);
  renderDevFormatExportArtifacts(null);
  renderDevFormatExportWarnings(null);
  renderDevFormatExportDiagramNotes(null);
  updateDevFormatExportFooter(null);
}

function renderDevFormatExportError(messageText) {
  latestDevFormatExport = null;
  if (devFormatExportSummary) {
    devFormatExportSummary.textContent = "AI Input Export를 완료하지 못했습니다.";
  }
  if (devFormatExportStartButton) {
    devFormatExportStartButton.disabled = !devFormatTargetPayload();
    devFormatExportStartButton.textContent = "Export 실행";
  }
  renderDevFormatExportStatus({
    label: "Export 실패",
    value: "오류",
    message: messageText || "AI Input Export 중 오류가 발생했습니다.",
    status: "danger",
  });
  renderDevFormatExportStats(null);
  renderDevFormatExportArtifacts(null);
  renderDevFormatExportWarnings(null);
  renderDevFormatExportDiagramNotes(null);
  updateDevFormatExportFooter(null);
}

function renderDevFormatExportResult(exportPayload) {
  const safeExport = exportPayload || {};
  latestDevFormatExport = safeExport;
  if (devFormatExportSummary) {
    devFormatExportSummary.textContent = `${safeExport.sourceName || "Full 정책서"} 변환 결과입니다.`;
  }
  if (devFormatExportStartButton) {
    devFormatExportStartButton.disabled = false;
    devFormatExportStartButton.textContent = "다시 Export";
  }
  const warnings = safeExport.warnings || {};
  const status = devFormatExportStatusClass(warnings);
  renderDevFormatExportStatus({
    label: "Export 결과",
    value: devFormatExportStatusLabel(warnings),
    message: devFormatExportStatusMessage(safeExport),
    status,
  });
  renderDevFormatExportStats(safeExport);
  renderDevFormatExportArtifacts(safeExport);
  renderDevFormatExportWarnings(warnings);
  renderDevFormatExportDiagramNotes(warnings);
  updateDevFormatExportFooter(safeExport);
}

function renderDevFormatExportStatus({ label, value, message, status }) {
  if (!devFormatExportStatus) return;
  devFormatExportStatus.className = `health-check-status-card ${status || ""}`.trim();
  devFormatExportStatus.innerHTML = "";
  const labelEl = document.createElement("span");
  labelEl.textContent = label || "Export";
  const valueEl = document.createElement("strong");
  valueEl.textContent = value || "-";
  const messageEl = document.createElement("p");
  messageEl.textContent = message || "";
  devFormatExportStatus.append(labelEl, valueEl, messageEl);
}

function renderDevFormatExportStats(exportPayload) {
  if (!devFormatExportStats) return;
  devFormatExportStats.innerHTML = "";
  if (!exportPayload) {
    devFormatExportStats.className = "dev-format-result-checklist empty";
    devFormatExportStats.textContent = "Export를 실행하면 생성 결과를 체크리스트로 표시합니다.";
    return;
  }
  devFormatExportStats.className = "dev-format-result-checklist";
  devFormatExportChecklistItems(exportPayload).forEach((item) => {
    const card = document.createElement("article");
    card.className = `dev-format-check-item ${item.state || "done"}`.trim();
    const marker = document.createElement("span");
    marker.className = "dev-format-check-marker";
    marker.textContent = item.state === "danger" ? "!" : item.state === "info" ? "i" : "✓";
    const label = document.createElement("strong");
    label.textContent = item.label;
    if (item.detail) {
      const detail = document.createElement("span");
      detail.textContent = item.detail;
      card.append(marker, label, detail);
    } else {
      card.append(marker, label);
    }
    devFormatExportStats.appendChild(card);
  });
}

function devFormatExportChecklistItems(exportPayload) {
  const counts = exportPayload?.counts || {};
  const warnings = exportPayload?.warnings || {};
  const blockingCount = Number(warnings.blockingCount || 0);
  const reviewCount = Number(warnings.reviewCount || 0);
  const diagramNoteCount = Number(warnings.diagramNotes?.actionCount || 0);
  const items = [
    { label: "Full 문서 확인", detail: exportPayload?.sourceName || "", state: "done" },
    { label: `User Case별 Markdown ${Number(counts.usecaseFiles || 0)}개 생성`, state: "done" },
    { label: `mapping.csv ${Number(counts.mappingRows || 0)} rows 생성`, state: "done" },
    { label: `diagrams ${Number(counts.diagramFiles || 0)}개 포함`, state: "done" },
    {
      label: `차단 경고 ${blockingCount}건`,
      detail: blockingCount > 0 ? "ZIP 전달 전 warnings.md를 확인하세요." : "핵심 정합성 기준을 통과했습니다.",
      state: blockingCount > 0 ? "danger" : "done",
    },
  ];
  if (reviewCount > 0) {
    items.push({ label: `검토 경고 ${reviewCount}건`, detail: "비차단 항목입니다. warnings.md에서 확인하세요.", state: "info" });
  }
  if (diagramNoteCount > 0) {
    items.push({ label: `다이어그램 참고 안내 ${diagramNoteCount}건`, detail: "원본 SVG 확인이 필요한 참고 항목입니다.", state: "info" });
  }
  return items;
}

function renderDevFormatExportArtifacts(exportPayload) {
  if (!devFormatExportArtifactList) return;
  const tree = exportPayload?.zipTree || null;
  if (devFormatExportArtifactCount) {
    devFormatExportArtifactCount.textContent = tree ? "ZIP" : "대기";
  }
  devFormatExportArtifactList.innerHTML = "";
  if (!tree) {
    devFormatExportArtifactList.className = "dev-format-zip-tree empty";
    devFormatExportArtifactList.textContent = "Export 결과를 기다리고 있습니다.";
    return;
  }
  devFormatExportArtifactList.className = "dev-format-zip-tree";
  devFormatExportArtifactList.appendChild(buildDevFormatZipTree(tree));
}

function buildDevFormatZipTree(tree) {
  const root = document.createElement("div");
  const rootName = document.createElement("strong");
  rootName.className = "dev-format-zip-root";
  rootName.textContent = tree.rootName || "export.zip";
  const list = document.createElement("ul");
  (tree.files || []).forEach((fileName) => {
    list.appendChild(devFormatZipTreeItem(fileName));
  });
  const usecaseCount = Number(tree.groups?.usecases?.count || 0);
  list.appendChild(devFormatZipTreeItem(`usecase_*.md ${usecaseCount}개`, "User Case별 Markdown"));
  const diagramFiles = Array.isArray(tree.groups?.diagrams?.files) ? tree.groups.diagrams.files : [];
  const diagramsItem = devFormatZipTreeItem("diagrams/", `${diagramFiles.length}개 SVG`);
  if (diagramFiles.length) {
    const nested = document.createElement("ul");
    diagramFiles.forEach((fileName) => nested.appendChild(devFormatZipTreeItem(fileName)));
    diagramsItem.appendChild(nested);
  }
  list.appendChild(diagramsItem);
  root.append(rootName, list);
  return root;
}

function devFormatZipTreeItem(name, note = "") {
  const item = document.createElement("li");
  const label = document.createElement("span");
  label.textContent = name;
  item.appendChild(label);
  if (note) {
    const meta = document.createElement("small");
    meta.textContent = note;
    item.appendChild(meta);
  }
  return item;
}

function renderDevFormatExportWarnings(warnings) {
  if (!devFormatExportWarningList) return;
  const sections = Array.isArray(warnings?.sections) ? warnings.sections : [];
  const total = Number(warnings?.totalCount || 0);
  if (devFormatExportWarningCount) {
    devFormatExportWarningCount.textContent = `${total}건`;
  }
  devFormatExportWarningList.innerHTML = "";
  if (!sections.length) {
    devFormatExportWarningList.className = "dev-format-warning-list empty";
    devFormatExportWarningList.textContent = warnings ? "핵심 정합성 경고가 없습니다." : "아직 검증 결과가 없습니다.";
    return;
  }
  devFormatExportWarningList.className = "dev-format-warning-list";
  sections.forEach((section) => {
    const card = document.createElement("article");
    card.className = `dev-format-warning-card ${section.tone || "review"}`.trim();
    const label = document.createElement("span");
    label.textContent = section.tone === "blocking" ? "차단 경고" : "검토 경고";
    const title = document.createElement("strong");
    title.textContent = `${section.label || "경고"} · ${Number(section.count || 0)}건`;
    card.append(label, title);
    devFormatExportWarningList.appendChild(card);
  });
}

function renderDevFormatExportDiagramNotes(warnings) {
  const notes = warnings?.diagramNotes || {};
  const items = Array.isArray(notes.items) ? notes.items : [];
  if (devFormatExportDiagramNoteCount) {
    devFormatExportDiagramNoteCount.textContent = `${items.length}건`;
  }
  if (devFormatExportDiagramNoteSection) {
    devFormatExportDiagramNoteSection.hidden = !items.length;
  }
  if (!devFormatExportDiagramNoteList) return;
  devFormatExportDiagramNoteList.innerHTML = "";
  if (!items.length) {
    devFormatExportDiagramNoteList.className = "dev-format-warning-list empty";
    devFormatExportDiagramNoteList.textContent = warnings ? "다이어그램 보강 안내가 없습니다." : "아직 검증 결과가 없습니다.";
    return;
  }
  devFormatExportDiagramNoteList.className = "dev-format-warning-list";
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "dev-format-warning-card info";
    const label = document.createElement("span");
    label.textContent = item.label || "다이어그램 안내";
    const message = document.createElement("strong");
    message.textContent = item.message || "원본 SVG 확인이 필요합니다.";
    card.append(label, message);
    const targets = Array.isArray(item.targets) ? item.targets.filter(Boolean) : [];
    if (targets.length) {
      const targetWrap = document.createElement("div");
      targetWrap.className = "dev-format-target-list";
      targets.forEach((target) => {
        const chip = document.createElement("code");
        chip.textContent = target;
        targetWrap.appendChild(chip);
      });
      card.appendChild(targetWrap);
    }
    const action = document.createElement("p");
    action.textContent = item.action || "warnings.md와 diagrams/*.svg를 함께 확인하세요.";
    card.appendChild(action);
    devFormatExportDiagramNoteList.appendChild(card);
  });
}

function updateDevFormatExportFooter(exportPayload) {
  if (devFormatExportFooter) {
    devFormatExportFooter.hidden = !exportPayload;
  }
  if (devFormatExportFooterSummary) {
    devFormatExportFooterSummary.textContent = exportPayload?.zipArtifact?.name
      ? `다운로드 파일: ${exportPayload.zipArtifact.name}`
      : "ZIP 다운로드 파일이 준비되면 여기에 표시됩니다.";
  }
  if (devFormatExportZipLink) {
    devFormatExportZipLink.href = exportPayload?.zipArtifact?.url || "#";
    if (exportPayload?.zipArtifact?.name) {
      devFormatExportZipLink.setAttribute("download", exportPayload.zipArtifact.name);
    } else {
      devFormatExportZipLink.removeAttribute("download");
    }
  }
}

function devFormatExportStatusClass(warnings) {
  if (Number(warnings?.blockingCount || 0) > 0 || warnings?.status === "blocked") return "danger";
  if (Number(warnings?.reviewCount || 0) > 0 || warnings?.status === "review") return "warn";
  return "success";
}

function devFormatExportStatusLabel(warnings) {
  if (Number(warnings?.blockingCount || 0) > 0 || warnings?.status === "blocked") return "확인 필요";
  if (Number(warnings?.reviewCount || 0) > 0 || warnings?.status === "review") return "검토 필요";
  return "변환 완료";
}

function devFormatExportStatusMessage(exportPayload) {
  const warnings = exportPayload?.warnings || {};
  if (Number(warnings.blockingCount || 0) > 0) {
    return `ZIP 다운로드 전 차단 경고 ${warnings.blockingCount}건을 먼저 확인해 주세요.`;
  }
  if (Number(warnings.reviewCount || 0) > 0) {
    return `변환은 완료되었습니다. 비차단 검토 경고 ${warnings.reviewCount}건은 warnings.md에서 확인하세요.`;
  }
  const diagramNoteCount = Number(warnings.diagramNotes?.actionCount || 0);
  if (diagramNoteCount > 0) {
    return `ZIP 다운로드가 준비되었습니다. 다이어그램 참고 안내 ${diagramNoteCount}건은 원본 SVG 확인용입니다.`;
  }
  return "ZIP 다운로드가 준비되었습니다. 차단 경고는 없습니다.";
}

async function startDevFormatExport() {
  const targetPayload = devFormatTargetPayload();
  if (!targetPayload) {
    renderDevFormatExportError("AI Input Export는 Full 버전 정책서에서만 실행할 수 있습니다.");
    return false;
  }
  devFormatExportInFlight = true;
  renderDevFormatExportLoading();
  updatePreviewMoreActionsVisibility();
  if (devFormatExportButton) devFormatExportButton.disabled = true;
  try {
    const response = await fetch(apiPath("/api/policies/dev-format-export"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(withClientSession(targetPayload)),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok || !data.export) {
      throw new Error(data.error || "AI Input Export를 완료하지 못했습니다.");
    }
    renderDevFormatExportResult(data.export);
    setMessage(`AI Input Export 완료: ${data.export.zipArtifact?.name || data.export.outputDir || selectedName}`);
    return true;
  } catch (error) {
    renderDevFormatExportError(error.message);
    setMessage(error.message || "AI Input Export 중 오류가 발생했습니다.", true);
    return false;
  } finally {
    devFormatExportInFlight = false;
    if (devFormatExportButton) devFormatExportButton.disabled = !devFormatTargetPayload();
    if (devFormatExportStartButton) devFormatExportStartButton.disabled = !devFormatTargetPayload();
  }
}

function openAlignmentCheckModal() {
  if (alignmentCheckModal) {
    alignmentCheckModal.hidden = false;
  }
  if (alignmentCheckInFlight) {
    renderAlignmentCheckLoading();
    return;
  }
  const cachedReport = cachedAlignmentCheckReport();
  if (cachedReport) {
    renderAlignmentCheckReport(cachedReport);
    return;
  }
  renderAlignmentCheckIntro();
}

function closeAlignmentCheckModal() {
  if (alignmentCheckModal) {
    alignmentCheckModal.hidden = true;
  }
}

async function startAlignmentCheck() {
  const targetPayload = alignmentCheckTargetPayload();
  if (!targetPayload) {
    renderAlignmentCheckError("분석-정책 정렬 Check 대상 정책서를 먼저 선택해 주세요.");
    return;
  }
  let payload;
  try {
    payload = await buildLlmControlledPayload(targetPayload);
    if (!payload) return;
  } catch (error) {
    renderAlignmentCheckError(error.message || "LLM 사용 인증에 실패했습니다.");
    return;
  }
  alignmentCheckInFlight = true;
  renderAlignmentCheckLoading();
  trackUserEvent("analysis_alignment_check_started", { selectedName });
  if (alignmentCheckButton) alignmentCheckButton.disabled = true;
  if (alignmentCheckStartButton) alignmentCheckStartButton.disabled = true;
  try {
    const response = await fetch(apiPath("/api/policies/analysis-alignment"), {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "분석-정책 정렬 Check 중 오류가 발생했습니다.");
    }
    const cacheKey = alignmentCheckCacheKey();
    if (cacheKey) {
      alignmentCheckReportsByPolicy.set(cacheKey, data.report);
    }
    renderAlignmentCheckReport(data.report);
    setMessage(`분석-정책 정렬 Check 완료: ${data.report.score}점 · ${data.report.judgement}`);
  } catch (error) {
    renderAlignmentCheckError(error.message);
  } finally {
    alignmentCheckInFlight = false;
    if (alignmentCheckButton) alignmentCheckButton.disabled = false;
    if (alignmentCheckStartButton) alignmentCheckStartButton.disabled = false;
  }
}

function alignmentCheckTargetPayload() {
  return selectedName ? { name: selectedName } : null;
}

function renderAlignmentCheckIntro() {
  latestAlignmentCheckReport = null;
  if (alignmentCheckSummary) {
    alignmentCheckSummary.textContent = "현황 분석 근거가 정책서에 반영되었는지, 정책 판단이 분석 근거로 설명되는지 양방향으로 점검합니다.";
  }
  if (alignmentCheckStartButton) {
    alignmentCheckStartButton.disabled = !alignmentCheckTargetPayload();
    alignmentCheckStartButton.textContent = "정렬 Check 시작";
  }
  renderAlignmentCheckStatus({
    label: "점검 기준",
    value: "분석 ↔ 정책 양방향",
    message: alignmentCheckTargetPayload()
      ? "벤치마킹, 고객 조사, 임직원 인터뷰, IA 분석, VoC 분석 근거와 정책서의 개요·유즈케이스·프로세스·기능·정책 항목을 비교합니다."
      : "문서 작업실에서 정책서를 선택한 뒤 실행할 수 있습니다.",
    status: alignmentCheckTargetPayload() ? "info" : "warn",
  });
  renderAlignmentCheckStats(null);
  renderAlignmentCheckSources([]);
  renderAlignmentCheckCards(alignmentCheckAnalysisList, alignmentCheckAnalysisCount, [], "분석 근거 반영 결과를 기다리고 있습니다.");
  renderAlignmentCheckCards(alignmentCheckPolicyList, alignmentCheckPolicyCount, [], "정책 요소 근거 결과를 기다리고 있습니다.");
  renderAlignmentCheckActions([]);
}

function renderAlignmentCheckLoading() {
  latestAlignmentCheckReport = null;
  if (alignmentCheckSummary) {
    alignmentCheckSummary.textContent = "현황 분석 근거 DB와 정책서 spec을 읽어 양방향 trace를 비교하고 있습니다.";
  }
  if (alignmentCheckStartButton) {
    alignmentCheckStartButton.disabled = true;
    alignmentCheckStartButton.textContent = "점검 중";
  }
  renderAlignmentCheckStatus({
    label: "점검 중",
    value: "처리 중",
    message: "분석 근거의 핵심 신호가 정책서에 반영되었는지, 정책 요소가 분석 근거로 설명되는지 확인합니다.",
    status: "loading",
  });
  renderAlignmentCheckStats(null);
  renderAlignmentCheckSources([]);
  renderAlignmentCheckCards(alignmentCheckAnalysisList, alignmentCheckAnalysisCount, [], "분석 근거를 비교하고 있습니다.");
  renderAlignmentCheckCards(alignmentCheckPolicyList, alignmentCheckPolicyCount, [], "정책 요소를 비교하고 있습니다.");
  renderAlignmentCheckActions([]);
}

function renderAlignmentCheckError(messageText) {
  latestAlignmentCheckReport = null;
  if (alignmentCheckSummary) {
    alignmentCheckSummary.textContent = "분석-정책 정렬 Check를 완료하지 못했습니다.";
  }
  if (alignmentCheckStartButton) {
    alignmentCheckStartButton.disabled = false;
    alignmentCheckStartButton.textContent = "정렬 Check 시작";
  }
  renderAlignmentCheckStatus({
    label: "점검 실패",
    value: "오류",
    message: messageText || "분석-정책 정렬 Check 중 오류가 발생했습니다.",
    status: "danger",
  });
  renderAlignmentCheckStats(null);
  renderAlignmentCheckSources([]);
  renderAlignmentCheckCards(alignmentCheckAnalysisList, alignmentCheckAnalysisCount, [], "정렬 Check 결과를 표시하지 못했습니다.");
  renderAlignmentCheckCards(alignmentCheckPolicyList, alignmentCheckPolicyCount, [], "정렬 Check 결과를 표시하지 못했습니다.");
  renderAlignmentCheckActions([]);
}

function renderAlignmentCheckReport(report) {
  const safeReport = report || {};
  latestAlignmentCheckReport = safeReport;
  const cacheKey = alignmentCheckCacheKey();
  if (cacheKey) {
    alignmentCheckReportsByPolicy.set(cacheKey, safeReport);
  }
  if (alignmentCheckSummary) {
    alignmentCheckSummary.textContent = "분석 근거 반영도와 정책 판단 근거를 확인하고, 보강할 trace 또는 본문 요소를 찾습니다.";
  }
  if (alignmentCheckStartButton) {
    alignmentCheckStartButton.disabled = false;
    alignmentCheckStartButton.textContent = "재점검";
  }
  renderAlignmentCheckStatus({
    label: "점검 결과",
    value: `${Number(safeReport.score || 0)}점 · ${safeReport.judgement || "-"}`,
    message: safeReport.summary || "분석-정책 정렬 Check를 완료했습니다.",
    status: alignmentCheckStatusClass(safeReport),
  });
  renderAlignmentCheckStats(safeReport);
  renderAlignmentCheckSources(safeReport.sourceCoverage || []);
  renderAlignmentCheckCards(
    alignmentCheckAnalysisList,
    alignmentCheckAnalysisCount,
    safeReport.analysisToPolicy || [],
    "분석 근거 반영 결과가 없습니다.",
    "analysis"
  );
  renderAlignmentCheckCards(
    alignmentCheckPolicyList,
    alignmentCheckPolicyCount,
    safeReport.policyToAnalysis || [],
    "정책 요소 근거 결과가 없습니다.",
    "policy"
  );
  renderAlignmentCheckActions(safeReport.actionItems || []);
}

function renderAlignmentCheckStatus({ label, value, message, status }) {
  if (!alignmentCheckStatus) return;
  alignmentCheckStatus.className = `health-check-status-card ${status || ""}`.trim();
  alignmentCheckStatus.innerHTML = "";
  const labelEl = document.createElement("span");
  labelEl.textContent = label || "점검 상태";
  const valueEl = document.createElement("strong");
  valueEl.textContent = value || "-";
  const messageEl = document.createElement("p");
  messageEl.innerHTML = lineBreakAfterSentence(message || "");
  alignmentCheckStatus.append(labelEl, valueEl, messageEl);
}

function renderAlignmentCheckStats(report) {
  if (!alignmentCheckStats) return;
  alignmentCheckStats.hidden = !report;
  alignmentCheckStats.innerHTML = "";
  if (!report) return;
  [
    { label: "총점", value: `${Number(report.score || 0)} / 100` },
    { label: "판정", value: report.judgement || "-" },
    { label: "분석 반영률", value: `${Number(report.analysisCoverageRate || 0)}%` },
    { label: "정책 근거율", value: `${Number(report.policyGroundingRate || 0)}%` },
    { label: "평가 방식", value: evaluationModeLabel(report.evaluationMode) },
    { label: "분석 근거", value: `${Number(report.analysisEvidenceCount || 0)}건` },
    { label: "정책 요소", value: `${Number(report.policyElementCount || 0)}건` },
  ].forEach((stat) => {
    const card = document.createElement("article");
    card.className = "health-check-stat-card";
    const label = document.createElement("span");
    label.textContent = stat.label;
    const value = document.createElement("strong");
    value.textContent = stat.value;
    card.append(label, value);
    alignmentCheckStats.appendChild(card);
  });
}

function renderAlignmentCheckSources(sources) {
  if (alignmentCheckSourceCount) {
    alignmentCheckSourceCount.textContent = `${Array.isArray(sources) ? sources.length : 0}개 출처`;
  }
  if (!alignmentCheckSourceList) return;
  alignmentCheckSourceList.innerHTML = "";
  if (!Array.isArray(sources) || sources.length === 0) {
    alignmentCheckSourceList.className = "alignment-check-source-list empty";
    alignmentCheckSourceList.textContent = "정렬 Check 결과를 기다리고 있습니다.";
    return;
  }
  alignmentCheckSourceList.className = "alignment-check-source-list";
  sources.forEach((source) => {
    const card = document.createElement("article");
    card.className = `alignment-check-source-card ${alignmentRateTone(source.coverageRate)}`;
    const head = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = source.sourceGroup || "분석 출처";
    const rate = document.createElement("span");
    rate.textContent = `${Number(source.coverageRate || 0)}%`;
    head.append(title, rate);
    const detail = document.createElement("p");
    detail.textContent = `반영 ${Number(source.covered || 0)} · 부분 ${Number(source.partial || 0)} · 보강 ${Number(source.missing || 0)} / 총 ${Number(source.total || 0)}건`;
    card.append(head, detail);
    alignmentCheckSourceList.appendChild(card);
  });
}

function renderAlignmentCheckCards(container, countEl, items, emptyText, mode = "analysis") {
  if (countEl) {
    countEl.textContent = `${Array.isArray(items) ? items.length : 0}건`;
  }
  if (!container) return;
  container.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    container.className = "alignment-check-list empty";
    container.textContent = emptyText || "결과가 없습니다.";
    return;
  }
  container.className = "alignment-check-list";
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = `alignment-check-card ${alignmentItemTone(item.status)}`;
    const top = document.createElement("div");
    top.className = "alignment-check-card-top";
    const titleWrap = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = mode === "analysis"
      ? `${item.sourceGroup || "분석"} · ${item.sourceName || item.id || "-"}`
      : `${item.sectionLabel || "정책"} · ${item.title || item.id || "-"}`;
    const meta = document.createElement("span");
    meta.textContent = `${item.statusLabel || item.status || "-"} · score ${Number(item.score || 0).toFixed(2)}`;
    titleWrap.append(title, meta);
    const badge = document.createElement("em");
    badge.textContent = item.statusLabel || item.status || "-";
    top.append(titleWrap, badge);
    const summary = document.createElement("p");
    summary.innerHTML = lineBreakAfterSentence(item.summary || item.text || item.rationale || "");
    const rationale = document.createElement("p");
    rationale.className = "alignment-check-rationale";
    rationale.textContent = item.rationale || "";
    card.append(top, summary, rationale);
    const chips = alignmentChips(item);
    if (chips.length) {
      const chipWrap = document.createElement("div");
      chipWrap.className = "alignment-check-chip-row";
      chips.forEach((chip) => {
        const chipEl = document.createElement("span");
        chipEl.textContent = chip;
        chipWrap.appendChild(chipEl);
      });
      card.appendChild(chipWrap);
    }
    const matches = Array.isArray(item.matches) ? item.matches : [];
    if (matches.length) {
      const matchList = document.createElement("div");
      matchList.className = "alignment-check-match-list";
      matches.slice(0, 3).forEach((match) => {
        const row = document.createElement("span");
        row.textContent = mode === "analysis"
          ? `${match.sectionLabel || "정책"} · ${match.title || match.id || "-"}`
          : `${match.sourceGroup || "분석"} · ${match.sourceName || match.id || "-"}`;
        matchList.appendChild(row);
      });
      card.appendChild(matchList);
    }
    container.appendChild(card);
  });
}

function renderAlignmentCheckActions(actions) {
  if (alignmentCheckActionCount) {
    alignmentCheckActionCount.textContent = `${Array.isArray(actions) ? actions.length : 0}건`;
  }
  if (!alignmentCheckActionList) return;
  alignmentCheckActionList.innerHTML = "";
  if (!Array.isArray(actions) || actions.length === 0) {
    alignmentCheckActionList.className = "alignment-check-list empty";
    alignmentCheckActionList.textContent = "보강 액션이 없습니다.";
    return;
  }
  alignmentCheckActionList.className = "alignment-check-list";
  actions.forEach((action) => {
    const card = document.createElement("article");
    card.className = `alignment-check-card ${action.priority === "P1" ? "danger" : "warn"}`;
    const top = document.createElement("div");
    top.className = "alignment-check-card-top";
    const titleWrap = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = action.title || "보강 액션";
    const target = document.createElement("span");
    target.textContent = action.target || "정책서";
    titleWrap.append(title, target);
    const badge = document.createElement("em");
    badge.textContent = action.priority || "P2";
    top.append(titleWrap, badge);
    const suggestion = document.createElement("p");
    suggestion.innerHTML = lineBreakAfterSentence(action.suggestion || "");
    card.append(top, suggestion);
    alignmentCheckActionList.appendChild(card);
  });
}

function alignmentChips(item) {
  const result = [];
  (Array.isArray(item.lenses) ? item.lenses : []).slice(0, 3).forEach((lens) => result.push(lens));
  (Array.isArray(item.signals) ? item.signals : []).slice(0, 2).forEach((signal) => result.push(signal));
  return result.filter(Boolean).slice(0, 5);
}

function alignmentCheckStatusClass(report) {
  const score = Number(report?.score || 0);
  if (score >= 82) return "success";
  if (score >= 65) return "warn";
  return "danger";
}

function alignmentRateTone(rate) {
  const value = Number(rate || 0);
  if (value >= 82) return "success";
  if (value >= 60) return "warn";
  return "danger";
}

function alignmentItemTone(status) {
  if (["covered", "grounded"].includes(status)) return "success";
  if (["partial", "weak"].includes(status)) return "warn";
  return "danger";
}

function openChannelPiStatusPage({ force = false } = {}) {
  if (!canCurrentUserViewChannelPiStatus()) {
    setMessage("채널 PI 현황은 관리자만 확인할 수 있습니다.", true);
    closeChannelPiStatusModal();
    return;
  }
  hideSelectionRevisionButton();
  closeSelectionRevisionModal();
  showChannelPiWorkspace();
  if (!force && latestChannelPiStatusReport) {
    renderChannelPiStatusReport(latestChannelPiStatusReport);
    return;
  }
  loadChannelPiStatus({ force });
}

async function loadChannelPiStatus({ force = false } = {}) {
  if (channelPiStatusInFlight) return;
  let payload = {};
  if (force) {
    try {
      payload = await buildLlmControlledPayload({});
      if (!payload) return;
    } catch (error) {
      renderChannelPiStatusError(error.message || "LLM 사용 인증에 실패했습니다.");
      return;
    }
  }
  channelPiStatusInFlight = true;
  startChannelPiProgress(force);
  renderChannelPiStatusLoading(force);
  if (channelPiStatusButton) channelPiStatusButton.disabled = true;
  if (channelPiDiagnoseButton) channelPiDiagnoseButton.disabled = true;
  try {
    const response = await fetch(apiPath(force ? "/api/channel-pi-status/diagnose" : "/api/channel-pi-status"), {
      method: force ? "POST" : "GET",
      headers: force ? jsonHeaders() : undefined,
      body: force ? JSON.stringify(payload) : undefined,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "채널 PI 현황을 불러오지 못했습니다.");
    }
    latestChannelPiStatusReport = data.report || {};
    renderChannelPiStatusReport(latestChannelPiStatusReport);
    if (latestChannelPiStatusReport.refreshError) {
      setMessage(`채널 PI 재진단은 실패했지만 직전 결과를 유지했습니다: ${latestChannelPiStatusReport.refreshError}`, true);
    } else {
      setMessage(`채널 PI 현황 ${force ? "재 진단" : "조회"} 완료: ${Number(latestChannelPiStatusReport.score || 0)}점 · ${latestChannelPiStatusReport.judgement || "-"}`);
    }
  } catch (error) {
    renderChannelPiStatusError(error.message);
  } finally {
    channelPiStatusInFlight = false;
    if (channelPiStatusButton) channelPiStatusButton.disabled = false;
    if (channelPiDiagnoseButton) channelPiDiagnoseButton.disabled = false;
  }
}

function startChannelPiProgress(force = false) {
  channelPiProgressStartedAt = Date.now();
  if (channelPiProgressTimer) {
    window.clearInterval(channelPiProgressTimer);
  }
  if (channelPiArea) {
    channelPiArea.dataset.loading = "true";
  }
  updateChannelPiProgress(force);
  channelPiProgressTimer = window.setInterval(() => {
    updateChannelPiProgress(force);
  }, 650);
}

function stopChannelPiProgress() {
  if (channelPiProgressTimer) {
    window.clearInterval(channelPiProgressTimer);
    channelPiProgressTimer = null;
  }
  channelPiProgressStartedAt = 0;
  if (channelPiArea) {
    delete channelPiArea.dataset.loading;
  }
  if (channelPiProgress) {
    channelPiProgress.hidden = true;
  }
}

function updateChannelPiProgress(force = false) {
  if (!channelPiProgress) return;
  const elapsed = Math.max(0, Date.now() - channelPiProgressStartedAt);
  const percent = Math.min(92, Math.round(8 + Math.log1p(elapsed / 600) * 24));
  const activeIndex = Math.min(
    CHANNEL_PI_PROGRESS_STEPS.length - 1,
    Math.floor((percent / 100) * CHANNEL_PI_PROGRESS_STEPS.length)
  );
  const active = CHANNEL_PI_PROGRESS_STEPS[activeIndex] || CHANNEL_PI_PROGRESS_STEPS[0];
  channelPiProgress.hidden = false;
  channelPiProgress.setAttribute("aria-busy", "true");
  if (channelPiProgressLabel) {
    channelPiProgressLabel.textContent = force ? "재진단 진행 중" : "진단 진행 중";
  }
  if (channelPiProgressTitle) {
    channelPiProgressTitle.textContent = active?.title || "채널 PI 현황을 점검하고 있습니다.";
  }
  if (channelPiProgressPercent) {
    channelPiProgressPercent.textContent = `${percent}%`;
  }
  if (channelPiProgressBar) {
    channelPiProgressBar.style.width = `${percent}%`;
  }
  if (channelPiProgressSteps) {
    channelPiProgressSteps.innerHTML = CHANNEL_PI_PROGRESS_STEPS.map((step, index) => {
      const state = index < activeIndex ? "done" : index === activeIndex ? "active" : "pending";
      return `
        <article class="${state}">
          <span>${escapeHtml(step.label)}</span>
          <strong>${escapeHtml(step.title)}</strong>
          <p>${escapeHtml(step.description)}</p>
        </article>
      `;
    }).join("");
  }
}

function renderChannelPiStatusLoading(force = false) {
  if (channelPiSummary) {
    channelPiSummary.textContent = force
      ? "최신 정책서와 현황 분석 지식을 다시 읽어 채널 PI 현황을 재진단하고 있습니다."
      : "저장된 채널 PI 현황을 불러오고, 없으면 새로 진단합니다.";
  }
  if (channelPiDiagnoseButton) {
    channelPiDiagnoseButton.textContent = force ? "재 진단 중" : "진단 준비";
    channelPiDiagnoseButton.disabled = true;
  }
  renderChannelPiStatusCard({
    label: "진단 중",
    value: "정렬 에이전트 실행",
    message: "정책서별 분석-정책 정렬 점검 결과를 모아 종합 현황으로 계산합니다.",
    status: "loading",
  });
  renderChannelPiStats(null);
  renderChannelPiStageFlow([]);
  renderChannelPiDimensions([]);
  renderChannelPiSources([]);
  renderChannelPiAnalysisItems([], null);
  renderChannelPiCrossValidation(null);
  renderChannelPiTopicRows([]);
  renderChannelPiActions([]);
}

function renderChannelPiStatusError(messageText) {
  stopChannelPiProgress();
  if (channelPiSummary) {
    channelPiSummary.textContent = "채널 PI 현황을 완료하지 못했습니다.";
  }
  if (channelPiDiagnoseButton) {
    channelPiDiagnoseButton.textContent = "재 진단";
    channelPiDiagnoseButton.disabled = false;
  }
  renderChannelPiStatusCard({
    label: "진단 실패",
    value: "오류",
    message: messageText || "채널 PI 현황 진단 중 오류가 발생했습니다.",
    status: "danger",
  });
  renderChannelPiStats(null);
  renderChannelPiStageFlow([]);
  renderChannelPiDimensions([]);
  renderChannelPiSources([]);
  renderChannelPiAnalysisItems([], null);
  renderChannelPiCrossValidation(null);
  renderChannelPiTopicRows([]);
  renderChannelPiActions([]);
}

function renderChannelPiStatusReport(report) {
  stopChannelPiProgress();
  const safeReport = report || {};
  if (channelPiSummary) {
    channelPiSummary.textContent = "새 정렬 에이전트가 정책서별 분석 근거 반영도와 정책 판단 근거율을 진단한 종합 결과입니다.";
  }
  if (channelPiDiagnoseButton) {
    channelPiDiagnoseButton.textContent = "재 진단";
    channelPiDiagnoseButton.disabled = false;
  }
  renderChannelPiStatusCard({
    label: safeReport.refreshError ? "저장된 결과" : safeReport.cached ? "저장된 결과" : "최신 진단",
    value: `${Number(safeReport.score || 0)}점 · ${safeReport.judgement || "-"}`,
    message: safeReport.refreshError
      ? `재진단 중 오류가 발생해 직전 정상 결과를 표시합니다. 오류: ${safeReport.refreshError}`
      : safeReport.summary || "채널 PI 현황 진단을 완료했습니다.",
    status: safeReport.refreshError ? "warn" : channelPiTone(safeReport.score),
  });
  renderChannelPiStats(safeReport);
  renderChannelPiStageFlow(safeReport.stageFlow || deriveChannelPiStageFlow(safeReport));
  renderChannelPiDimensions(safeReport.dimensions || []);
  renderChannelPiSources(safeReport.sourceCoverage || []);
  renderChannelPiAnalysisItems(safeReport.analysisItemCoverage || [], safeReport.analysisItemCoverageSummary || null);
  renderChannelPiCrossValidation(safeReport.crossValidation || null);
  renderChannelPiTopicRows(safeReport.topicRows || []);
  renderChannelPiActions(safeReport.priorityActions || []);
}

function renderChannelPiStatusCard({ label, value, message, status }) {
  if (!channelPiStatusCard) return;
  channelPiStatusCard.className = `channel-pi-status-card ${status || ""}`.trim();
  channelPiStatusCard.innerHTML = "";
  const labelEl = document.createElement("span");
  labelEl.textContent = label || "진단 상태";
  const valueEl = document.createElement("strong");
  valueEl.textContent = value || "-";
  const messageEl = document.createElement("p");
  messageEl.innerHTML = lineBreakAfterSentence(message || "");
  channelPiStatusCard.append(labelEl, valueEl, messageEl);
}

function renderChannelPiStats(report) {
  if (!channelPiStats) return;
  channelPiStats.innerHTML = "";
  if (!report) {
    channelPiStats.hidden = true;
    return;
  }
  channelPiStats.hidden = false;
  const evidence = report.evidence || {};
  const requirements = report.requirements || {};
  [
    { label: "종합 점수", value: `${Number(report.score || 0)} / 100` },
    { label: "판정", value: report.judgement || "-" },
    { label: "정책서", value: `${Number(report.topicCount || 0)}개` },
    { label: "진단 방식", value: `${channelPiAgentDisplayName(report.alignmentAgent)} · ${evaluationModeLabel(report.evaluationMode)}` },
    { label: "분석 근거", value: `${Number(evidence.analysisEvidenceCount || 0)}건` },
    { label: "요구사항", value: `${Number(requirements.detailCount || 0)}건` },
  ].forEach((stat) => {
    const card = document.createElement("article");
    card.className = "channel-pi-stat-card";
    const label = document.createElement("span");
    label.textContent = stat.label;
    const value = document.createElement("strong");
    value.textContent = stat.value;
    card.append(label, value);
    channelPiStats.appendChild(card);
  });
}

function channelPiAgentDisplayName(value) {
  const raw = String(value || "").trim();
  if (!raw) return "분석-정책 정렬";
  if (/analysis-policy|alignment check/i.test(raw)) return "분석-정책 정렬";
  if (raw === "분석-정책 정렬 진단" || raw === "분석-정책 정렬 Check") return "분석-정책 정렬";
  return raw;
}

function renderChannelPiStageFlow(stages) {
  if (!channelPiStageFlow) return;
  const fallbackStages = [
    { index: "01", title: "현황 분석", metric: "분석 근거", description: "분석 자료를 정책 판단 근거로 정리합니다." },
    { index: "02", title: "과제 정의", metric: "전략 과제", description: "분석 내용을 통합채널 과제로 압축합니다." },
    { index: "03", title: "요구사항", metric: "상세 기준", description: "과제 방향을 요구사항으로 구조화합니다." },
    { index: "04", title: "정책서", metric: "실행 정책", description: "요구사항과 분석 근거를 정책 기준으로 완성합니다." },
  ];
  const items = Array.isArray(stages) && stages.length ? stages : fallbackStages;
  channelPiStageFlow.innerHTML = "";
  items.slice(0, 4).forEach((stage, index) => {
    const card = document.createElement("article");
    card.className = "channel-pi-stage-card";
    const number = document.createElement("span");
    number.textContent = stage.index || String(index + 1).padStart(2, "0");
    const title = document.createElement("strong");
    title.textContent = stage.title || "-";
    const metric = document.createElement("em");
    metric.textContent = stage.metric || "";
    const description = document.createElement("p");
    description.innerHTML = lineBreakAfterSentence(stage.description || "");
    card.append(number, title, metric, description);
    channelPiStageFlow.appendChild(card);
  });
}

function deriveChannelPiStageFlow(report) {
  const evidence = report?.evidence || {};
  const requirements = report?.requirements || {};
  return [
    {
      index: "01",
      title: "현황 분석",
      metric: `${Number(evidence.analysisEvidenceCount || 0)}건`,
      description: "벤치마킹, 고객 조사, 임직원 인터뷰, IA, VoC 분석을 정책 판단의 근거로 정리합니다.",
    },
    {
      index: "02",
      title: "과제 정의",
      metric: "12개",
      description: "분석 내용을 통합채널 관점의 전략 과제와 실행 방향으로 압축합니다.",
    },
    {
      index: "03",
      title: "요구사항",
      metric: `${Number(requirements.detailCount || 0)}건`,
      description: "과제 방향을 상세 요구사항과 trace 기준으로 구조화합니다.",
    },
    {
      index: "04",
      title: "정책서",
      metric: `${Number(report?.topicCount || 0)}개`,
      description: "요구사항과 분석 근거가 정책서의 유즈케이스, 프로세스, 기능, 정책에 반영되는지 점검합니다.",
    },
  ];
}

function renderChannelPiDimensions(dimensions) {
  if (channelPiDimensionCount) {
    channelPiDimensionCount.textContent = `${Array.isArray(dimensions) ? dimensions.length : 0}개 축`;
  }
  if (!channelPiDimensionList) return;
  channelPiDimensionList.innerHTML = "";
  if (!Array.isArray(dimensions) || dimensions.length === 0) {
    channelPiDimensionList.className = "channel-pi-dimension-list empty";
    channelPiDimensionList.textContent = "진단 결과를 기다리고 있습니다.";
    return;
  }
  channelPiDimensionList.className = "channel-pi-dimension-list";
  dimensions.forEach((dimension) => {
    const card = document.createElement("article");
    card.className = `channel-pi-dimension-card ${dimension.status || channelPiTone(dimension.score)}`;
    const head = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = dimension.title || "진단 축";
    const score = document.createElement("span");
    score.textContent = `${Number(dimension.score || 0)}점`;
    head.append(title, score);
    const bar = document.createElement("div");
    bar.className = "channel-pi-meter";
    const fill = document.createElement("span");
    fill.style.width = `${Math.max(0, Math.min(100, Number(dimension.score || 0)))}%`;
    bar.appendChild(fill);
    const description = document.createElement("p");
    description.innerHTML = lineBreakAfterSentence(dimension.description || "");
    card.append(head, bar, description);
    channelPiDimensionList.appendChild(card);
  });
}

function renderChannelPiSources(sources) {
  const visibleSources = channelPiVisibleSources(sources);
  if (channelPiSourceCount) {
    channelPiSourceCount.textContent = `${visibleSources.length}개 출처`;
  }
  if (!channelPiSourceList) return;
  channelPiSourceList.innerHTML = "";
  if (!visibleSources.length) {
    channelPiSourceList.className = "channel-pi-source-list empty";
    channelPiSourceList.textContent = "분석 출처별 결과를 기다리고 있습니다.";
    return;
  }
  channelPiSourceList.className = "channel-pi-source-list";
  visibleSources.forEach((source) => {
    const card = document.createElement("article");
    card.className = `channel-pi-source-card ${source.status || channelPiTone(source.coverageRate)}`;
    const head = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = source.sourceGroup || "분석 출처";
    const rate = document.createElement("span");
    rate.textContent = `${Number(source.coverageRate || 0)}%`;
    head.append(title, rate);
    const detail = document.createElement("p");
    detail.textContent = `반영 ${Number(source.covered || 0)} · 부분 ${Number(source.partial || 0)} · 보강 ${Number(source.missing || 0)} / 총 ${Number(source.total || 0)}건`;
    card.append(head, detail);
    channelPiSourceList.appendChild(card);
  });
}

function channelPiVisibleSources(sources) {
  if (!Array.isArray(sources)) return [];
  return sources.filter((source) => !CHANNEL_PI_EXCLUDED_SOURCE_GROUPS.has(String(source?.sourceGroup || "").trim()));
}

function renderChannelPiAnalysisItems(items, summary) {
  const rows = Array.isArray(items) ? items : [];
  const safeSummary = summary || {};
  if (channelPiAnalysisItemCount) {
    const total = Number(safeSummary.total ?? rows.length ?? 0);
    const covered = Number(safeSummary.covered || 0);
    const partial = Number(safeSummary.partial || 0);
    const missing = Number(safeSummary.missing || 0);
    channelPiAnalysisItemCount.textContent = total
      ? `반영 ${covered} · 부분 ${partial} · 미반영 ${missing}`
      : "0건";
  }
  if (!channelPiAnalysisItemList) return;
  channelPiAnalysisItemList.innerHTML = "";
  if (!rows.length) {
    channelPiAnalysisItemList.className = "channel-pi-analysis-list empty";
    channelPiAnalysisItemList.textContent = "현황 분석 항목별 진단 결과를 기다리고 있습니다.";
    return;
  }
  channelPiAnalysisItemList.className = "channel-pi-analysis-list";
  rows.forEach((item) => {
    const card = document.createElement("article");
    card.className = `channel-pi-analysis-card ${channelPiCoverageTone(item.status)}`;

    const head = document.createElement("div");
    head.className = "channel-pi-analysis-head";
    const titleWrap = document.createElement("div");
    const source = document.createElement("span");
    source.textContent = [item.sourceGroup, item.sourceName].filter(Boolean).join(" · ") || "현황 분석";
    const summaryText = document.createElement("strong");
    summaryText.textContent = item.summary || "분석 항목";
    titleWrap.append(source, summaryText);
    const badge = document.createElement("em");
    badge.textContent = `${item.statusLabel || "-"} · ${Number(item.score || 0)}점`;
    head.append(titleWrap, badge);

    const handled = document.createElement("p");
    handled.className = "channel-pi-analysis-handled";
    handled.innerHTML = lineBreakAfterSentence(item.howHandled || item.coverageLabel || "");

    const matchGrid = document.createElement("div");
    matchGrid.className = "channel-pi-analysis-match-grid";
    matchGrid.append(
      channelPiAnalysisMatchBlock("요구사항 후보", item.requirementMatches || [], "requirement"),
      channelPiAnalysisMatchBlock("정책서 반영 위치", item.policyMatches || [], "policy")
    );

    const recommendation = document.createElement("p");
    recommendation.className = "channel-pi-analysis-recommendation";
    recommendation.innerHTML = lineBreakAfterSentence(item.recommendation || "");

    card.append(head, handled, matchGrid, recommendation);
    channelPiAnalysisItemList.appendChild(card);
  });
}

function channelPiAnalysisMatchBlock(titleText, matches, mode) {
  const block = document.createElement("div");
  block.className = "channel-pi-analysis-match";
  const title = document.createElement("span");
  title.textContent = titleText;
  block.appendChild(title);
  const rows = Array.isArray(matches) ? matches.slice(0, 3) : [];
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.textContent = "직접 후보 없음";
    block.appendChild(empty);
    return block;
  }
  rows.forEach((match) => {
    const row = document.createElement("p");
    if (mode === "requirement") {
      row.textContent = `${match.detailId || "-"} · ${match.detailName || match.topic || "-"} · ${Number(match.score || 0).toFixed(2)}`;
    } else {
      row.textContent = `${match.topic || "-"} · ${match.sectionLabel || "-"} · ${match.id || "-"} · ${match.title || "-"} · ${Number(match.score || 0).toFixed(2)}`;
    }
    block.appendChild(row);
  });
  return block;
}

function channelPiCoverageTone(status) {
  if (status === "covered") return "success";
  if (status === "partial") return "warn";
  return "danger";
}

function renderChannelPiCrossValidation(crossValidation) {
  const safeData = crossValidation || {};
  const findings = Array.isArray(safeData.findings) ? safeData.findings : [];
  if (channelPiCrossCount) {
    const trusted = Number(safeData.trustedCovered || 0);
    const review = Number(safeData.reviewNeeded || 0);
    channelPiCrossCount.textContent = crossValidation ? `안정 ${trusted} · 재확인 ${review}` : "0건";
  }
  if (channelPiCrossSummary) {
    channelPiCrossSummary.textContent = crossValidation
      ? safeData.summary || "양방향 교차검증을 완료했습니다."
      : "교차검증 결과를 기다리고 있습니다.";
  }
  if (!channelPiCrossList) return;
  channelPiCrossList.innerHTML = "";
  if (!findings.length) {
    channelPiCrossList.className = "channel-pi-cross-list empty";
    channelPiCrossList.textContent = crossValidation ? "교차검증 알림이 없습니다." : "교차검증 결과를 기다리고 있습니다.";
    return;
  }
  channelPiCrossList.className = "channel-pi-cross-list";
  findings.forEach((finding) => {
    const card = document.createElement("article");
    card.className = `channel-pi-cross-card ${finding.priority === "P1" ? "danger" : "warn"}`;
    const head = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = finding.title || "교차검증 알림";
    const priority = document.createElement("span");
    priority.textContent = finding.priority || "P2";
    head.append(title, priority);

    const summary = document.createElement("p");
    summary.className = "channel-pi-cross-evidence";
    summary.textContent = [finding.sourceGroup, finding.sourceName, finding.summary].filter(Boolean).join(" · ");

    const match = document.createElement("div");
    match.className = "channel-pi-cross-match";
    const requirement = document.createElement("p");
    requirement.textContent = `요구사항 후보: ${finding.requirementTopic || "-"} · ${finding.requirementElement || "-"} · ${Number(finding.requirementScore || 0).toFixed(2)}`;
    const policy = document.createElement("p");
    const traceConfidence = finding.policyTraceConfidenceLabel
      ? ` · Trace ${finding.policyTraceConfidenceLabel} ${Number(finding.policyTraceConfidenceScore || 0)}%`
      : "";
    policy.textContent = `정책서 후보: ${finding.policyTopic || "-"} · ${finding.policyElement || "-"} · ${Number(finding.policyScore || 0).toFixed(2)}${traceConfidence}`;
    match.append(requirement, policy);

    const reason = document.createElement("p");
    reason.innerHTML = lineBreakAfterSentence(finding.reason || "");
    const recommendation = document.createElement("em");
    recommendation.innerHTML = lineBreakAfterSentence(finding.recommendation || "");
    card.append(head, summary, match, reason, recommendation);
    channelPiCrossList.appendChild(card);
  });
}

function renderChannelPiTopicRows(rows) {
  if (channelPiTopicCount) {
    channelPiTopicCount.textContent = `${Array.isArray(rows) ? rows.length : 0}개 정책서`;
  }
  if (!channelPiTopicTableBody) return;
  channelPiTopicTableBody.innerHTML = "";
  if (!Array.isArray(rows) || rows.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 8;
    cell.textContent = "정책서별 정렬 현황을 기다리고 있습니다.";
    row.appendChild(cell);
    channelPiTopicTableBody.appendChild(row);
    return;
  }
  rows.forEach((item) => {
    const row = document.createElement("tr");
    row.className = channelPiTone(item.score);
    const titleCell = document.createElement("td");
    const title = document.createElement("strong");
    title.textContent = item.topic || item.policyFile || "-";
    const meta = document.createElement("span");
    meta.textContent = `${item.version || "-"} · ${item.templateLabel || "정책서"}`;
    titleCell.append(title, meta);
    [
      `${Number(item.score || 0)}점`,
      `${Number(item.analysisRequirementCoverageRate || 0)}%`,
      `${Number(item.requirementPolicyTraceRate || 0)}%`,
      `${Number(item.analysisCoverageRate || 0)}%`,
      `${Number(item.traceContinuityRate || 0)}%`,
      `${Number(item.traceConfidenceScore || item.traceSchemaCompletenessRate || 0)}% · ${item.traceConfidenceLabel || "미확인"}`,
      item.status || item.judgement || "-",
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    });
    row.insertBefore(titleCell, row.firstChild);
    channelPiTopicTableBody.appendChild(row);
  });
}

function renderChannelPiActions(actions) {
  if (channelPiActionCount) {
    channelPiActionCount.textContent = `${Array.isArray(actions) ? actions.length : 0}건`;
  }
  if (!channelPiActionList) return;
  channelPiActionList.innerHTML = "";
  if (!Array.isArray(actions) || actions.length === 0) {
    channelPiActionList.className = "channel-pi-action-list empty";
    channelPiActionList.textContent = "우선 보강 액션이 없습니다.";
    return;
  }
  channelPiActionList.className = "channel-pi-action-list";
  actions.forEach((action) => {
    const card = document.createElement("article");
    card.className = `channel-pi-action-card ${action.priority === "P1" ? "danger" : "warn"}`;
    const head = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = action.title || "보강 액션";
    const priority = document.createElement("span");
    priority.textContent = action.priority || "P2";
    head.append(title, priority);
    const target = document.createElement("em");
    target.textContent = action.target || action.topic || "정책서";
    const suggestion = document.createElement("p");
    suggestion.innerHTML = lineBreakAfterSentence(action.suggestion || "");
    card.append(head, target, suggestion);
    channelPiActionList.appendChild(card);
  });
}

function channelPiTone(score) {
  const value = Number(score || 0);
  if (value >= 82) return "success";
  if (value >= 65) return "warn";
  return "danger";
}

function selectedHealthCheckRevisionItems() {
  const checked = [...(healthCheckModal?.querySelectorAll(".health-check-select:checked") || [])];
  const sections = Array.isArray(latestHealthCheckReport?.sections) ? latestHealthCheckReport.sections : [];
  return checked.map((input, index) => {
    const sectionId = input.dataset.sectionId || "";
    const itemId = input.dataset.itemId || "";
    const section = sections.find((candidate) => String(candidate.id || "") === sectionId) || {};
    const item = (Array.isArray(section.items) ? section.items : []).find((candidate) => String(candidate.id || "") === itemId) || {};
    const note = input.closest(".health-check-section-detail-row")?.querySelector(".health-check-auto-note")?.value?.trim() || "";
    return { index: index + 1, section, item, note };
  }).filter((entry) => entry.item && Object.keys(entry.item).length > 0);
}

function updateHealthCheckRevisionState() {
  const checkedCount = healthCheckModal?.querySelectorAll(".health-check-select:checked").length || 0;
  const blocked = Boolean(latestHealthCheckReport?.resultBlocked);
  if (healthCheckSelectionSummary) {
    if (!latestHealthCheckReport) {
      healthCheckSelectionSummary.textContent = "Health Check 결과에서 FAIL 항목을 선택하면 수정 Agent에게 전달할 수 있습니다.";
    } else if (!canCurrentUserWritePolicies()) {
      healthCheckSelectionSummary.textContent = "조회 권한은 Health Check 결과 확인만 가능하며 자동 보완은 실행할 수 없습니다.";
    } else if (selectedPolicyCompleted()) {
      healthCheckSelectionSummary.textContent = "작성 완료 상태에서는 완료 취소 후 Health Check 자동 보완을 요청할 수 있습니다.";
    } else if (blocked && checkedCount === 0) {
      healthCheckSelectionSummary.textContent = "GateKeeper 또는 산출물 동기화 경고가 있습니다. 본문 FAIL 항목을 선택하면 수정 Agent에게 전달할 수 있습니다.";
    } else if (blocked) {
      healthCheckSelectionSummary.textContent = `${checkedCount}개 FAIL 항목을 선택했습니다. 경고가 있으므로 보완 후 전체 Health Check를 다시 실행해 주세요.`;
    } else if (checkedCount === 0) {
      healthCheckSelectionSummary.textContent = "FAIL 항목을 체크하고, 필요하면 항목별 수정 방향 메모를 입력하세요.";
    } else {
      healthCheckSelectionSummary.textContent = `${checkedCount}개 FAIL 항목을 선택했습니다. 선택 항목만 수정 Agent에게 전달합니다.`;
    }
  }
  if (healthCheckRevisionButton) {
    healthCheckRevisionButton.disabled = checkedCount === 0 || !selectedName || selectedPolicyCompleted() || !canCurrentUserWritePolicies();
  }
  if (healthCheckRecheckButton) {
    healthCheckRecheckButton.disabled = !latestHealthCheckReport || (!checkedCount && failedHealthCheckItemIds().length === 0);
  }
  if (healthCheckExportButton) {
    healthCheckExportButton.disabled = !latestHealthCheckReport;
  }
  if (healthCheckArtifactRepairButton) {
    const hasArtifactIssue = healthCheckHasArtifactSyncIssue(latestHealthCheckReport);
    healthCheckArtifactRepairButton.textContent = healthCheckNeedsHtmlSpecSync(latestHealthCheckReport)
      ? "HTML 기준 spec 보정"
      : "산출물 동기화 복구";
    healthCheckArtifactRepairButton.hidden = !hasArtifactIssue;
    healthCheckArtifactRepairButton.disabled = !hasArtifactIssue || !selectedName || selectedPolicyCompleted() || !canCurrentUserWritePolicies();
  }
}

function failedHealthCheckItemIds() {
  const sections = Array.isArray(latestHealthCheckReport?.sections) ? latestHealthCheckReport.sections : [];
  const ids = [];
  sections.forEach((section) => {
    (Array.isArray(section.items) ? section.items : []).forEach((item) => {
      const maxScore = Number(item.maxScore ?? item.max_score ?? 2);
      if (item?.id && Number(item.score || 0) < maxScore && !ids.includes(item.id)) {
        ids.push(item.id);
      }
    });
  });
  return ids;
}

function buildHealthCheckRevisionInstruction(selectedItems = []) {
  const lines = [
    "Health Check FAIL 항목 일괄 자동 보완 요청입니다.",
    "",
    "[수정 대상]",
    "- 아래 사용자가 선택한 FAIL 항목만 보완하세요.",
    "- 여러 항목이 같은 장/표/정책 항목을 가리키면 한 번에 자연스럽게 통합 보완하세요.",
    "- 선택하지 않은 Health Check 항목을 이유로 문서 전체를 재작성하지 마세요.",
    "",
  ];
  selectedItems.forEach(({ index, section, item, note }) => {
    const sectionName = String(section?.name || "Health Check 영역").trim();
    const itemId = String(item?.id || "-").trim();
    const question = String(item?.question || "체크 항목").trim();
    const evidence = String(item?.evidence || "확인된 근거가 없습니다.").trim();
    const suggestion = String(item?.suggestion || "추가 보완 제안이 없습니다.").trim();
    const relatedLocation = String(item?.relatedLocation || "문서 본문").trim();
    const score = Object.prototype.hasOwnProperty.call(item || {}, "score") ? `${item.score}/${item.maxScore ?? item.max_score ?? 2}` : "-";
    lines.push(
      `${index}. [${sectionName}] ${itemId} · ${question}`,
      `   - 관련 위치: ${relatedLocation}`,
      `   - 점수: ${score}`,
      `   - 판단 근거: ${evidence}`,
      `   - 보완 제안: ${suggestion}`,
      note ? `   - 사용자 수정 방향 메모: ${note}` : "",
      "",
    );
  });
  lines.push(
    "[보완 원칙]",
    "- 전체 문서를 새로 쓰지 말고, 위 선택 항목과 관련된 장/표/정책 항목만 수정하세요.",
    "- 템플릿 구조와 CSS는 변경하지 마세요.",
    "- 요구사항 원문을 그대로 복사하지 말고 업무 흐름과 정책 판단 기준으로 재구성하세요.",
    "- 정책 항목은 실제 값, 조건, 횟수, 시간, 상태, 예외, 고지, 이력 기준 중 하나 이상이 드러나게 작성하세요.",
    "- 보완 후 선택한 Health Check 항목이 PASS가 될 수 있도록 근거가 문서 본문에 명확히 남아야 합니다.",
  );
  return lines.join("\n");
}

function renderHealthCheckSectionChart(sections) {
  if (!healthCheckSectionChart) return;
  healthCheckSectionChart.className = "health-check-section-chart";
  healthCheckSectionChart.innerHTML = "";
  const evaluatedSections = (Array.isArray(sections) ? sections : []).filter((section) =>
    Object.prototype.hasOwnProperty.call(section, "score")
  );
  if (!evaluatedSections.length) {
    healthCheckSectionChart.hidden = true;
    return;
  }
  healthCheckSectionChart.hidden = false;
  evaluatedSections.forEach((section) => {
    const maxScore = Math.max(1, Number(section.maxScore ?? section.max_score ?? 10));
    const score = Math.max(0, Math.min(maxScore, Number(section.score || 0)));
    const percent = Math.round((score / maxScore) * 100);
    const row = document.createElement("div");
    row.className = `health-check-chart-row ${healthCheckSectionTone(score)}`;
    const label = document.createElement("span");
    label.className = "health-check-chart-label";
    label.textContent = section.name || "점검 영역";
    const bar = document.createElement("span");
    bar.className = "health-check-chart-bar";
    bar.setAttribute("aria-hidden", "true");
    const fill = document.createElement("span");
    fill.style.width = `${percent}%`;
    bar.appendChild(fill);
    const value = document.createElement("strong");
    value.className = "health-check-chart-value";
    value.textContent = `${score} / ${maxScore}`;
    row.append(label, bar, value);
    healthCheckSectionChart.appendChild(row);
  });
}

function renderHealthCheckGates(gates) {
  if (healthCheckGateCount) {
    healthCheckGateCount.textContent = `${Array.isArray(gates) ? gates.length : 0}건`;
  }
  if (!healthCheckGateList) return;
  healthCheckGateList.innerHTML = "";
  if (!Array.isArray(gates) || gates.length === 0) {
    healthCheckGateList.className = "health-check-gate-list empty";
    healthCheckGateList.textContent = "필수 게이트 결과를 기다리고 있습니다.";
    return;
  }
  healthCheckGateList.className = "health-check-gate-list";
  gates.forEach((gate) => {
    const card = document.createElement("article");
    card.className = `health-check-gate-card ${gate.passed ? "pass" : "fail"}`;
    const badge = document.createElement("span");
    badge.textContent = gate.passed ? "통과" : "미통과";
    const title = document.createElement("strong");
    title.textContent = `${gate.id || "-"} · ${gate.description || ""}`;
    const reason = document.createElement("p");
    reason.textContent = gate.gatekeeper
      ? gate.summary || gate.suggestion || gate.reason || "평가 품질 GateKeeper 결과입니다."
      : gate.passed
        ? "필수 기준을 충족했습니다."
        : gate.suggestion || gate.reason || "보완이 필요합니다.";
    card.append(badge, title, reason);
    healthCheckGateList.appendChild(card);
  });
}

function healthCheckGatesWithGatekeeper(report) {
  const gates = Array.isArray(report?.mandatoryGates) ? [...report.mandatoryGates] : [];
  const gatekeeper = report?.gatekeeper;
  if (gatekeeper && typeof gatekeeper === "object") {
    gates.push({
      id: "GK",
      description: `Health Check GateKeeper · ${gatekeeper.grade || "-"}등급`,
      passed: Boolean(gatekeeper.passed),
      reason: gatekeeper.summary || "",
      suggestion: gatekeeper.summary || "",
      summary: gatekeeper.summary || "",
      gatekeeper: true,
    });
  }
  const drift = report?.artifactDrift;
  if (drift && typeof drift === "object") {
    gates.push({
      id: "ART",
      description: `산출물 동기화 · ${healthCheckArtifactDriftLabel(drift)}`,
      passed: drift.status === "pass",
      reason: drift.summary || "",
      suggestion: drift.summary || "",
      summary: drift.summary || "",
      gatekeeper: true,
    });
  }
  return gates;
}

function healthCheckGatekeeperLabel(gatekeeper) {
  if (!gatekeeper || typeof gatekeeper !== "object") return "-";
  const grade = gatekeeper.grade || "-";
  return `${grade} · ${gatekeeper.passed ? "통과" : "보완 필요"}`;
}

function healthCheckArtifactDriftLabel(drift) {
  if (!drift || typeof drift !== "object") return "-";
  if (drift.htmlSpecSyncNeeded) return "Spec 보정 필요";
  if (drift.status === "pass") return "통과";
  if (drift.status === "warn") return "주의";
  if (drift.status === "fail") return "차단";
  if (drift.status === "skipped") return "미적용";
  return String(drift.status || "-");
}

function healthCheckTrendLabel(trend) {
  if (!trend || typeof trend !== "object") return "-";
  const delta = trend.scoreDelta;
  if (delta === null || delta === undefined) return `${Number(trend.versionCount || 0)}개 버전`;
  const sign = Number(delta) >= 0 ? "+" : "";
  return `${Number(trend.versionCount || 0)}개 · ${sign}${delta}점`;
}

function renderHealthCheckItems(items, report = null) {
  const plan = report?.remediationPlan && typeof report.remediationPlan === "object" ? report.remediationPlan : null;
  if (plan) {
    renderHealthCheckRemediationPlan(plan, items);
    return;
  }
  if (healthCheckItemCount) {
    healthCheckItemCount.textContent = `${Array.isArray(items) ? items.length : 0}건`;
  }
  if (!healthCheckItemList) return;
  healthCheckItemList.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    healthCheckItemList.className = "health-check-item-list empty";
    healthCheckItemList.textContent = "보완 항목이 없습니다.";
    return;
  }
  healthCheckItemList.className = "health-check-item-list";
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = `health-check-item-card ${String(item.priority || "P3").toLowerCase()}`;
    const top = document.createElement("div");
    top.className = "health-check-item-top";
    const priority = document.createElement("span");
    priority.textContent = item.priority || "P3";
    const score = document.createElement("em");
    score.textContent = `${Number(item.score || 0)}점`;
    top.append(priority, score);
    const title = document.createElement("strong");
    title.textContent = item.title || "보완 항목";
    const location = document.createElement("p");
    location.textContent = `위치: ${item.targetLocation || "문서 본문"}`;
    const suggestion = document.createElement("p");
    suggestion.innerHTML = lineBreakAfterSentence(item.suggestion || item.evidence || "");
    card.append(top, title, location, suggestion);
    healthCheckItemList.appendChild(card);
  });
}

function renderHealthCheckRemediationPlan(plan, fallbackItems = []) {
  if (!healthCheckItemList) return;
  const immediate = Array.isArray(plan.immediate) ? plan.immediate : [];
  const potential = Array.isArray(plan.potential) ? plan.potential : [];
  const artifact = Array.isArray(plan.artifactSync) ? plan.artifactSync : [];
  const newlyDetected = Array.isArray(plan.newlyDetected) ? plan.newlyDetected : [];
  const repeated = Array.isArray(plan.repeated) ? plan.repeated : [];
  const improved = Array.isArray(plan.improved) ? plan.improved : [];
  const totalCount = immediate.length + potential.length + artifact.length;
  if (healthCheckItemCount) {
    healthCheckItemCount.textContent = `${totalCount || (Array.isArray(fallbackItems) ? fallbackItems.length : 0)}건`;
  }
  healthCheckItemList.innerHTML = "";
  healthCheckItemList.className = "health-check-item-list health-check-remediation-plan";
  const summary = document.createElement("article");
  summary.className = "health-check-plan-summary";
  const summaryTitle = document.createElement("strong");
  summaryTitle.textContent = "보완 전략 요약";
  const summaryText = document.createElement("p");
  summaryText.textContent = plan.summary || "Health Check 보완 항목을 처리 우선순위별로 분리했습니다.";
  const chips = document.createElement("div");
  chips.className = "health-check-plan-chips";
  [
    ["즉시", immediate.length],
    ["잠재", potential.length],
    ["동기화", artifact.length],
    ["신규", newlyDetected.length],
    ["반복", repeated.length],
    ["개선", improved.length],
  ].forEach(([label, count]) => {
    const chip = document.createElement("span");
    chip.textContent = `${label} ${count}`;
    chips.appendChild(chip);
  });
  const guidance = document.createElement("p");
  guidance.textContent = plan.guidance || "즉시 보완 항목부터 처리하고 재점검으로 반복 항목이 줄었는지 확인하세요.";
  summary.append(summaryTitle, summaryText, chips, guidance);
  healthCheckItemList.appendChild(summary);

  const groups = [
    {
      title: "즉시 보완 항목",
      description: "필수 Gate, 0점 항목, 요구사항·계층 연결처럼 바로 보완해야 하는 항목입니다.",
      className: "immediate",
      items: immediate,
      empty: "즉시 보완 항목이 없습니다.",
    },
    {
      title: "잠재 보완 항목",
      description: "부분 충족 항목입니다. 즉시 보완 후에도 점수 상승을 막을 수 있어 함께 확인해야 합니다.",
      className: "potential",
      items: potential,
      empty: "잠재 보완 항목이 없습니다.",
    },
    {
      title: "산출물 동기화 이슈",
      description: "본문 품질과 별개로 HTML, spec, BPMN, Trace 산출물 정합성을 확인해야 하는 항목입니다.",
      className: "artifact",
      items: artifact,
      empty: "산출물 동기화 이슈가 없습니다.",
    },
  ];
  groups.forEach((group) => {
    healthCheckItemList.appendChild(renderHealthCheckPlanGroup(group));
  });

  if (newlyDetected.length || repeated.length || improved.length) {
    const changeGroup = renderHealthCheckPlanGroup({
      title: "재점검 변화",
      description: "이번 재점검에서 새로 드러난 항목, 반복 지적된 항목, 개선된 항목입니다.",
      className: "change",
      items: [
        ...newlyDetected.map((item) => ({ ...item, historyStatus: item.historyStatus || "new" })),
        ...repeated.map((item) => ({ ...item, historyStatus: item.historyStatus || "repeated" })),
        ...improved.map((item) => ({ ...item, historyStatus: item.historyStatus || "resolved" })),
      ],
      empty: "재점검 변화가 없습니다.",
    });
    healthCheckItemList.appendChild(changeGroup);
  }
}

function renderHealthCheckPlanGroup(group) {
  const wrap = document.createElement("section");
  wrap.className = `health-check-plan-group ${group.className || ""}`.trim();
  const head = document.createElement("div");
  head.className = "health-check-plan-group-head";
  const titleWrap = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = group.title;
  const description = document.createElement("p");
  description.textContent = group.description || "";
  titleWrap.append(title, description);
  const count = document.createElement("span");
  count.textContent = `${Array.isArray(group.items) ? group.items.length : 0}건`;
  head.append(titleWrap, count);
  wrap.appendChild(head);
  const list = document.createElement("div");
  list.className = "health-check-plan-group-list";
  if (!Array.isArray(group.items) || group.items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "health-check-plan-empty";
    empty.textContent = group.empty || "항목이 없습니다.";
    list.appendChild(empty);
  } else {
    group.items.forEach((item) => list.appendChild(renderHealthCheckPlanItem(item)));
  }
  wrap.appendChild(list);
  return wrap;
}

function renderHealthCheckPlanItem(item) {
  const card = document.createElement("article");
  card.className = `health-check-item-card ${String(item.priority || "P3").toLowerCase()}`;
  const top = document.createElement("div");
  top.className = "health-check-item-top";
  const left = document.createElement("div");
  left.className = "health-check-item-badges";
  const priority = document.createElement("span");
  priority.textContent = item.priority || "P3";
  left.appendChild(priority);
  const history = healthCheckHistoryLabel(item.historyStatus, item.recheckStatus);
  if (history) {
    const historyBadge = document.createElement("span");
    historyBadge.className = `history ${String(item.historyStatus || "initial").toLowerCase()}`;
    historyBadge.textContent = history;
    left.appendChild(historyBadge);
  }
  const score = document.createElement("em");
  const maxScore = Number(item.maxScore || 2);
  score.textContent = `${Number(item.score || item.currentScore || 0)} / ${maxScore}`;
  top.append(left, score);
  const title = document.createElement("strong");
  title.textContent = item.title || "보완 항목";
  const meta = document.createElement("p");
  meta.textContent = `${item.section || "Health Check"} · ${item.targetLocation || "문서 본문"}`;
  const suggestion = document.createElement("p");
  suggestion.innerHTML = lineBreakAfterSentence(item.suggestion || item.evidence || "");
  card.append(top, title, meta, suggestion);
  return card;
}

function healthCheckHistoryLabel(historyStatus, recheckStatus) {
  if (recheckStatus === "reused") return "이전 결과 유지";
  if (recheckStatus === "rechecked") return "재점검";
  if (historyStatus === "new") return "신규";
  if (historyStatus === "regressed") return "신규 악화";
  if (historyStatus === "repeated") return "반복";
  if (historyStatus === "resolved") return "개선";
  if (historyStatus === "artifact") return "동기화";
  if (historyStatus === "graph") return "Trace";
  return "";
}

function healthCheckStatusClass(report) {
  const score = Number(report?.score || 0);
  if (report?.resultBlocked) return "danger";
  if (!report?.mandatoryGatePassed || score < 70) return "danger";
  if (report?.gatekeeper && report.gatekeeper.passed === false) return "warn";
  if (score < 90) return "warn";
  return "success";
}

function healthCheckSectionTone(score) {
  const value = Number(score || 0);
  if (value >= 9) return "success";
  if (value >= 7) return "warn";
  return "danger";
}

function healthCheckSectionItemTone(score) {
  const value = Number(score || 0);
  if (value >= 2) return "success";
  if (value >= 1) return "warn";
  return "danger";
}

function openDocumentAnalysisModal() {
  const analysis = analyzePreviewDocument();
  renderDocumentAnalysis(analysis);
  if (documentAnalysisModal) {
    documentAnalysisModal.hidden = false;
  }
}

function closeDocumentAnalysisModal() {
  if (documentAnalysisModal) {
    documentAnalysisModal.hidden = true;
  }
}

function analyzePreviewDocument() {
  let doc;
  try {
    doc = previewFrame?.contentDocument;
  } catch (error) {
    doc = null;
  }
  if (!doc || !doc.body) {
    return {
      ok: false,
      title: "분석할 문서가 없습니다.",
      summary: "문서 작업실에서 정책서를 선택한 뒤 다시 문서 분석을 실행해 주세요.",
      items: documentAnalysisEmptyItems(),
      healthItems: documentHealthEmptyItems(),
    };
  }

  const html = doc.documentElement?.outerHTML || "";
  const historyTotal = collectHistoryItems(doc).length;
  const transitionTotal = countRowsInTablesByHeader(doc, "전이 이벤트");
  const subFunctionTotal = countSubFunctionItems(doc);
  const actorTotal = countUniqueIdsInTablesByHeader(doc, "액터 ID", "ACT");
  const usecaseStats = countUsecaseDefinitions(doc);
  const usecaseTotal = usecaseStats.total;
  const processTargetUsecaseTotal = usecaseStats.processTargetTotal;
  const stateTotal = countUniqueIdsInTablesByHeader(doc, "상태 코드", "ST");
  const processTotal = countUniqueIdsInTablesByHeader(doc, "프로세스 ID", "PR");
  const functionTotal = countUniqueIdsInTablesByHeader(doc, "기능 ID", "FN");
  const policyTotal = countUniqueIdsInTablesByHeader(doc, "정책 ID", "PG");
  const policyItemTotal = countPolicyItems(doc);
  const processFunctionLinks = countRelatedIdsInTablesByHeaders(doc, "프로세스 ID", "관련 기능", "FN");
  const processPolicyLinks = countRelatedIdsInTablesByHeaders(doc, "프로세스 ID", "관련 정책", "PG");
  const items = [
    analysisMetric("문서 히스토리 수", historyTotal, "문서 변경 이력"),
    analysisMetric("용어 수", countUniqueIdsInTablesByHeader(doc, "용어 ID", "TM"), "용어 정의 표 기준"),
    analysisMetric("액터 수", actorTotal, "액터 정의 표 기준"),
    analysisMetric("유즈케이스 수", usecaseTotal, `유즈케이스 정의 표 기준 · Y ${processTargetUsecaseTotal}개`),
    analysisMetric("상태 수", stateTotal, "상태 코드 표 기준"),
    analysisMetric("상태 전이 케이스", transitionTotal, "상태 전이표 행 기준"),
    analysisMetric("프로세스 수", processTotal, "프로세스 목록 표 기준"),
    analysisMetric("기능 수", functionTotal, "기능 목록 표 기준"),
    analysisMetric("세부 기능 구성 수", subFunctionTotal, "기능 목록의 세부 항목"),
    analysisMetric("정책 수", policyTotal, "정책 목록 표 기준"),
    analysisMetric("정책 항목 수", policyItemTotal, "정책 상세 항목 기준"),
  ];
  const healthItems = [
    healthMetric("액터당 유즈케이스", ratio(usecaseTotal, actorTotal), "유즈케이스 수 / 액터 수"),
    healthMetric("유즈케이스당 프로세스", ratio(processTotal, processTargetUsecaseTotal || usecaseTotal), "프로세스 수 / 프로세스 대상 유즈케이스"),
    healthMetric("프로세스당 기능 수", ratio(processFunctionLinks.targetCount || functionTotal, processFunctionLinks.rowCount || processTotal), "프로세스 관련 기능 ID 기준"),
    healthMetric("기능당 세부 기능 구성 수", ratio(subFunctionTotal, functionTotal), "세부 기능 구성 수 / 기능 수"),
    healthMetric("프로세스당 정책 수", ratio(processPolicyLinks.targetCount || policyTotal, processPolicyLinks.rowCount || processTotal), "프로세스 관련 정책 ID 기준"),
    healthMetric("정책당 정책 항목 수", ratio(policyItemTotal, policyTotal), "정책 항목 수 / 정책 수"),
  ];
  const total = items.reduce((sum, item) => sum + item.value, 0);
  return {
    ok: true,
    title: "문서 구조 분석 완료",
    summary: `${previewTitle?.textContent || "선택한 문서"}에서 ${items.length}개 구조 지표와 ${healthItems.length}개 Health 지표를 확인했습니다. 총 ${total.toLocaleString("ko-KR")}개 항목 기준입니다.`,
    items,
    healthItems,
  };
}

function renderDocumentAnalysis(analysis) {
  if (documentAnalysisSummary) {
    documentAnalysisSummary.textContent = analysis.summary;
  }
  if (!documentAnalysisGrid) return;
  documentAnalysisGrid.innerHTML = "";
  analysis.items.forEach((item) => {
    const card = document.createElement("article");
    card.className = `document-analysis-card${analysis.ok ? "" : " muted"}`;
    const label = document.createElement("span");
    label.textContent = item.label;
    const value = document.createElement("strong");
    value.textContent = item.displayValue || item.value.toLocaleString("ko-KR");
    const hint = document.createElement("em");
    hint.textContent = item.hint;
    card.append(label, value, hint);
    documentAnalysisGrid.appendChild(card);
  });
  if (!documentHealthGrid) return;
  documentHealthGrid.innerHTML = "";
  (analysis.healthItems || []).forEach((item) => {
    const card = document.createElement("article");
    card.className = `document-health-card${analysis.ok ? "" : " muted"}`;
    const label = document.createElement("span");
    label.textContent = item.label;
    const value = document.createElement("strong");
    value.textContent = item.displayValue || item.value.toLocaleString("ko-KR");
    const hint = document.createElement("em");
    hint.textContent = item.hint;
    card.append(label, value, hint);
    documentHealthGrid.appendChild(card);
  });
}

function documentAnalysisEmptyItems() {
  return [
    "문서 히스토리 수",
    "용어 수",
    "액터 수",
    "유즈케이스 수",
    "상태 수",
    "상태 전이 케이스",
    "프로세스 수",
    "기능 수",
    "세부 기능 구성 수",
    "정책 수",
    "정책 항목 수",
  ].map((label) => analysisMetric(label, 0, "문서 선택 후 계산"));
}

function documentHealthEmptyItems() {
  return [
    "액터당 유즈케이스",
    "유즈케이스당 프로세스",
    "프로세스당 기능 수",
    "기능당 세부 기능 구성 수",
    "프로세스당 정책 수",
    "정책당 정책 항목 수",
  ].map((label) => healthMetric(label, 0, "문서 선택 후 계산"));
}

function analysisMetric(label, value, hint) {
  const numericValue = Number(value);
  return {
    label,
    value: Number.isFinite(numericValue) ? numericValue : 0,
    hint,
  };
}

function healthMetric(label, value, hint) {
  const numericValue = Number(value);
  const safeValue = Number.isFinite(numericValue) ? numericValue : 0;
  return {
    label,
    value: safeValue,
    displayValue: safeValue.toFixed(1),
    hint,
  };
}

function ratio(numerator, denominator) {
  const bottom = Number(denominator);
  if (!Number.isFinite(bottom) || bottom <= 0) return 0;
  const top = Number(numerator);
  if (!Number.isFinite(top) || top <= 0) return 0;
  return top / bottom;
}

function countUniqueDocumentIds(html, prefix) {
  const escapedPrefix = String(prefix || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`(?:^|[^A-Z0-9])(${escapedPrefix}-[A-Z0-9]+-[A-Z0-9-]+)`, "g");
  const values = new Set();
  let match;
  while ((match = pattern.exec(html)) !== null) {
    values.add(match[1].replace(/[은는이가을를의와과로]$/, ""));
  }
  return values.size;
}

function countUniqueIdsInTablesByHeader(doc, idHeader, idPrefix) {
  const values = new Set();
  [...doc.querySelectorAll("table")].forEach((table) => {
    const headers = [...table.querySelectorAll("thead th")].map((header) => cleanWorkspaceText(header.textContent));
    const idIndex = headers.indexOf(idHeader);
    if (idIndex < 0) return;
    [...table.querySelectorAll("tbody tr")].forEach((row) => {
      const cell = row.querySelectorAll("td")[idIndex];
      extractDocumentIds(cell?.textContent || "", idPrefix).forEach((id) => values.add(id));
    });
  });
  return values.size;
}

function countUsecaseDefinitions(doc) {
  const usecaseIds = new Set();
  const processTargetUsecaseIds = new Set();
  [...doc.querySelectorAll("table")].forEach((table) => {
    const headers = [...table.querySelectorAll("thead th")].map((header) => cleanWorkspaceText(header.textContent));
    const idIndex = headers.indexOf("유즈케이스 ID");
    if (idIndex < 0) return;
    const processTargetIndex = headers.indexOf("프로세스 정의 대상");
    [...table.querySelectorAll("tbody tr")].forEach((row) => {
      const cells = row.querySelectorAll("td");
      const ids = extractDocumentIds(cells[idIndex]?.textContent || "", "US");
      ids.forEach((id) => usecaseIds.add(id));
      const targetValue = cleanWorkspaceText(cells[processTargetIndex]?.textContent || "").toUpperCase();
      if (targetValue === "Y") {
        ids.forEach((id) => processTargetUsecaseIds.add(id));
      }
    });
  });
  return {
    total: usecaseIds.size,
    processTargetTotal: processTargetUsecaseIds.size,
  };
}

function countPolicyItems(doc) {
  const values = new Set();
  [...doc.querySelectorAll(".policy-item-title, .policy-item")].forEach((item) => {
    extractDocumentIds(item.textContent || "", "PI").forEach((id) => values.add(id));
  });
  if (values.size > 0) return values.size;
  return countUniqueDocumentIds(doc.documentElement?.outerHTML || "", "PI");
}

function countRelatedIdsInTablesByHeaders(doc, rowIdHeader, targetHeader, idPrefix) {
  const sourceIds = new Set();
  const links = new Set();
  [...doc.querySelectorAll("table")].forEach((table) => {
    const headers = [...table.querySelectorAll("thead th")].map((header) => cleanWorkspaceText(header.textContent));
    const rowIndex = headers.indexOf(rowIdHeader);
    const targetIndex = headers.indexOf(targetHeader);
    if (rowIndex < 0 || targetIndex < 0) return;
    [...table.querySelectorAll("tbody tr")].forEach((row) => {
      const cells = row.querySelectorAll("td");
      const rowId = cleanWorkspaceText(cells[rowIndex]?.textContent || "");
      if (!rowId) return;
      sourceIds.add(rowId);
      extractDocumentIds(cells[targetIndex]?.innerHTML || cells[targetIndex]?.textContent || "", idPrefix).forEach((targetId) => {
        links.add(`${rowId}::${targetId}`);
      });
    });
  });
  return { rowCount: sourceIds.size, targetCount: links.size };
}

function extractDocumentIds(value, prefix) {
  const text = String(value || "");
  const escapedPrefix = String(prefix || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`(?:^|[^A-Z0-9])(${escapedPrefix}-[A-Z0-9]+-[A-Z0-9-]+)`, "g");
  const values = [];
  const seen = new Set();
  let match;
  while ((match = pattern.exec(text)) !== null) {
    const id = match[1].replace(/[은는이가을를의와과로]$/, "");
    if (seen.has(id)) continue;
    seen.add(id);
    values.push(id);
  }
  return values;
}

function countRowsInTablesByHeader(doc, headerLabel) {
  const rowSignatures = new Set();
  [...doc.querySelectorAll("table")].forEach((table) => {
    const headerText = cleanWorkspaceText(table.querySelector("thead")?.textContent || "");
    if (!headerText.includes(headerLabel)) return;
    [...table.querySelectorAll("tbody tr")].forEach((row) => {
      rowSignatures.add(cleanWorkspaceText(row.textContent || ""));
    });
  });
  return rowSignatures.size;
}

function countSubFunctionItems(doc) {
  const subFunctionKeys = new Set();
  [...doc.querySelectorAll("table")].forEach((table) => {
    const headers = [...table.querySelectorAll("thead th")].map((header) => cleanWorkspaceText(header.textContent));
    if (!headers.includes("기능 ID") || !headers.includes("세부 기능 구성")) return;
    const functionIdIndex = headers.indexOf("기능 ID");
    const detailIndex = headers.indexOf("세부 기능 구성");
    [...table.querySelectorAll("tbody tr")].forEach((row) => {
      const cells = row.querySelectorAll("td");
      const functionId = extractDocumentIds(cells[functionIdIndex]?.textContent || "", "FN")[0] || `row-${subFunctionKeys.size + 1}`;
      const cell = cells[detailIndex];
      if (!cell) return;
      const htmlItems = cell.innerHTML
        .split(/<br\s*\/?>/i)
        .map((item) => cleanWorkspaceText(item.replace(/<[^>]+>/g, " ")))
        .filter(Boolean);
      if (htmlItems.length > 0) {
        htmlItems.forEach((item) => subFunctionKeys.add(`${functionId}::${item}`));
        return;
      }
      const textItem = cleanWorkspaceText(cell.textContent);
      if (textItem) {
        subFunctionKeys.add(`${functionId}::${textItem}`);
      }
    });
  });
  return subFunctionKeys.size;
}

function collectPolicyValues(doc) {
  const items = [...doc.querySelectorAll(".policy-item")];
  return items
    .map((item) => {
      const title = cleanWorkspaceText(item.querySelector(".policy-item-title")?.textContent || "");
      const content = cleanWorkspaceText(item.querySelector(".policy-item-content")?.textContent || "");
      const group = cleanWorkspaceText(item.closest(".policy-group")?.querySelector("h4")?.textContent || "");
      const body = `${title} ${content}`;
      return {
        title: title.replace(/^•\s*/, "") || "정책 항목",
        body: content || "-",
        meta: classifyPolicyValue(body),
        group,
        suggestion: `${title.replace(/^•\s*/, "") || "선택한 정책 항목"}의 정책값을 샘플처럼 값·조건·횟수·시간·채널 중심으로 더 명확하게 보완해줘.`,
      };
    })
    .filter((item) => item.title || item.body);
}

function collectTbdItems(doc, policyValues) {
  const vaguePatterns = ["TBD", "검토 필요", "추후 협의", "정책에 따라", "가능하도록 한다", "관련 부서 확인 필요"];
  const fromPolicies = policyValues
    .filter((item) => vaguePatterns.some((pattern) => `${item.title} ${item.body}`.includes(pattern)))
    .map((item) => ({
      level: "issue",
      title: item.title,
      body: item.body,
      suggestion: `${item.title}의 모호한 표현을 실제 정책값, 결정 주체, 결정 필요 사유, 결정 기한이 드러나도록 보완해줘.`,
    }));
  const text = cleanWorkspaceText(doc.body?.innerText || "");
  if (!text.includes("TBD")) return fromPolicies;
  const lines = text
    .split(/(?<=다\.|요\.|음\.|\n)/)
    .map((line) => cleanWorkspaceText(line))
    .filter((line) => line.includes("TBD"))
    .slice(0, 5)
    .map((line) => ({
      level: "issue",
      title: "TBD 확인 필요",
      body: line,
      suggestion: "문서 안의 TBD 항목을 결정 주체, 결정 필요 사유, 결정 기한과 함께 정리해줘.",
    }));
  return [...fromPolicies, ...lines];
}

function collectHistoryItems(doc) {
  const heading = [...doc.querySelectorAll("h2, h3")].find((item) => item.textContent.includes("문서 히스토리"));
  if (!heading) return [];
  const table = nextElementByTag(heading, "TABLE");
  if (!table) return [];
  const rows = [...table.querySelectorAll("tbody tr")]
    .map((row) => [...row.querySelectorAll("td")].map((cell) => cleanWorkspaceText(cell.textContent)))
    .filter((cells) => cells.length >= 2)
    .map((cells) => ({
      level: "good",
      title: cells[0] || "변경 이력",
      body: cells.slice(1, 4).filter(Boolean).join(" · "),
    }));
  return rows.reverse();
}

function buildWorkspaceComments(doc, policyValues, tbdItems, historyItems) {
  const text = cleanWorkspaceText(doc.body?.innerText || "");
  const comments = [];
  const genericPolicyNames = policyValues.filter((item) => /적용 기준|예외 기준|이력 기준|기본 적용 기준/.test(item.title));
  const longPolicyItems = policyValues.filter((item) => item.body.length > 180);
  const authMentioned = /인증|본인확인|인증번호|PASS/.test(text);
  const authValueDefined = policyValues.some((item) => /인증 수단|인증 가능 횟수|인증번호 유효시간|유효시간/.test(item.title));

  if (policyValues.length === 0) {
    comments.push({
      level: "issue",
      title: "정책 상세 항목 없음",
      body: "정책 목록은 있어도 세부 정책값이 없으면 상세 설계 기준으로 쓰기 어렵습니다.",
      suggestion: "프로세스와 기능에 필요한 정책을 정의하고, 정책별 세부 항목과 항목별 값을 작성해줘.",
    });
  } else {
    comments.push({
      level: "good",
      title: "정책값 추출 완료",
      body: `${policyValues.length}개 정책 상세 항목을 정책값 보드에 모았습니다.`,
    });
  }
  if (tbdItems.length > 0) {
    comments.push({
      level: "issue",
      title: "미정 또는 모호한 표현 있음",
      body: `${tbdItems.length}개 항목이 TBD 또는 모호한 표현을 포함합니다.`,
      suggestion: "미정·보완 항목을 실제 정책값 또는 결정 필요 항목으로 정리해줘.",
    });
  }
  if (genericPolicyNames.length > 2) {
    comments.push({
      level: "warn",
      title: "정책 항목명이 일반적임",
      body: "'적용 기준/예외 기준/이력 기준'보다 인증 수단, 제한 기간, 저장 항목처럼 값 중심 이름이 좋습니다.",
      suggestion: "정책 항목명을 샘플처럼 실제 기능 동작값 중심으로 바꿔줘.",
    });
  }
  if (longPolicyItems.length > 0) {
    comments.push({
      level: "warn",
      title: "정책 내용이 장황함",
      body: `${longPolicyItems.length}개 정책 항목이 길게 작성되어 값과 조건이 한눈에 보이지 않습니다.`,
      suggestion: "긴 정책 내용을 항목별 값, 조건, 예외로 분리해서 짧게 정리해줘.",
    });
  }
  if (authMentioned && !authValueDefined) {
    comments.push({
      level: "warn",
      title: "인증 정책값 확인 필요",
      body: "문서에 인증 업무가 나오지만 인증 수단, 가능 횟수, 유효시간 같은 값이 약해 보입니다.",
      suggestion: "인증 관련 정책에 인증 수단, 인증 가능 횟수, 인증번호 유효시간, 실패 처리 기준을 추가해줘.",
    });
  }
  if (historyItems.length === 0) {
    comments.push({
      level: "warn",
      title: "문서 히스토리 확인 필요",
      body: "수정/보완 이력을 추적할 수 있는 문서 히스토리가 보이지 않습니다.",
    });
  }
  return comments.slice(0, 7);
}

function setAssistList(target, items) {
  if (!target) return;
  if (!items.length) {
    target.classList.add("empty");
    target.innerHTML = "표시할 항목이 없습니다.";
    return;
  }
  target.classList.remove("empty");
  target.innerHTML = items
    .map((item) => {
      const level = item.level || "good";
      const button = item.suggestion
        ? `<button class="assist-request-button" type="button" data-suggestion="${escapeHtml(item.suggestion)}">수정 요청에 담기</button>`
        : "";
      return `<div class="assist-item ${escapeHtml(level)}"><strong>${escapeHtml(item.title || "확인 항목")}</strong><p>${escapeHtml(item.body || "")}</p>${button}</div>`;
    })
    .join("");
  installAssistSuggestionButtons(target);
}

function setPolicyValueList(target, items) {
  if (!target) return;
  if (!items.length) {
    target.classList.add("empty");
    target.innerHTML = "정책 상세 항목을 모아 보여줍니다.";
    return;
  }
  target.classList.remove("empty");
  target.innerHTML = items
    .map(
      (item) => `<div class="policy-value-item"><span>${escapeHtml(item.meta || "정책값")}</span><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.body)}</p><button class="assist-request-button" type="button" data-suggestion="${escapeHtml(item.suggestion)}">이 항목 보완</button></div>`
    )
    .join("");
  installAssistSuggestionButtons(target);
}

function installAssistSuggestionButtons(root) {
  root.querySelectorAll(".assist-request-button").forEach((button) => {
    button.addEventListener("click", () => {
      if (!revisionRequest) return;
      revisionRequest.value = button.dataset.suggestion || "";
      revisionRequest.focus();
      setMessage("수정 요청 메모에 보완 방향을 담았습니다. 필요하면 문장을 다듬고 Agent를 실행해 주세요.");
    });
  });
}

function setAssistCount(target, value) {
  if (target) target.textContent = String(value || 0);
}

function updateEditorCommentToolControls() {
  if (editorCommentSearchInput && editorCommentSearchInput.value !== editorCommentSearchQuery) {
    editorCommentSearchInput.value = editorCommentSearchQuery;
  }
  editorCommentStatusFilterInputs.forEach((input) => {
    input.checked = editorCommentStatusFilterValues.has(input.value);
  });
  if (editorCommentFilterLabel) {
    const selectedStatuses = EDITOR_COMMENT_STATUSES.filter((status) => editorCommentStatusFilterValues.has(status));
    editorCommentFilterLabel.textContent = selectedStatuses.length === EDITOR_COMMENT_STATUSES.length
      ? "전체 상태"
      : selectedStatuses.length
        ? selectedStatuses.join(", ")
        : "상태 미선택";
  }
  editorCommentSortButtons.forEach((button) => {
    button.setAttribute("aria-pressed", String((button.dataset.commentSort || "recent") === editorCommentSortOrder));
  });
  if (editorCommentSortLabel) {
    editorCommentSortLabel.textContent = editorCommentSortOrder === "oldest" ? "오래된 코멘트순" : "최근 코멘트순";
  }
}

function editorCommentSearchText(comment = {}) {
  const replyText = Array.isArray(comment.replies)
    ? comment.replies.map((reply) => [
      reply.note,
      reply.author,
      reply.authorName,
      reply.createdAt,
      reply.updatedAt,
    ].map((value) => cleanWorkspaceText(value || "")).filter(Boolean).join(" ")).join(" ")
    : "";
  return [
    comment.note,
    comment.status,
    comment.author,
    comment.authorName,
    comment.targetText,
    comment.blockText,
    comment.title,
    comment.targetKind,
    comment.kind,
    Array.isArray(comment.headingPath) ? comment.headingPath.join(" ") : "",
    comment.createdAt,
    comment.updatedAt,
    replyText,
  ].map((value) => cleanWorkspaceText(value || "")).filter(Boolean).join(" ").toLowerCase();
}

function compareEditorCommentsByDate(a, b) {
  const aTime = Date.parse(a?.createdAt || a?.updatedAt || "") || 0;
  const bTime = Date.parse(b?.createdAt || b?.updatedAt || "") || 0;
  return editorCommentSortOrder === "oldest" ? aTime - bTime : bTime - aTime;
}

function compareEditorCommentsRecentFirst(a, b) {
  const aTime = Date.parse(a?.createdAt || a?.updatedAt || "") || 0;
  const bTime = Date.parse(b?.createdAt || b?.updatedAt || "") || 0;
  return bTime - aTime;
}

function closeEditorCommentActionMenus(exceptMenu = null) {
  document.querySelectorAll(".editor-comment-action-menu[open]").forEach((menu) => {
    if (menu !== exceptMenu) menu.open = false;
  });
}

function focusEditorCommentReplyInput(commentId = "") {
  if (!commentId) return;
  window.setTimeout(() => {
    const card = [...(editorCommentList?.querySelectorAll("[data-comment-id]") || [])]
      .find((candidate) => candidate.dataset.commentId === commentId);
    card?.querySelector("[data-comment-reply-input]")?.focus();
  }, 0);
}

function selectEditorComment(commentId = "", options = {}) {
  const id = String(commentId || "");
  if (!id) return;
  const comment = editorComments.find((item) => item.id === id);
  if (!comment) return;
  selectedEditorCommentId = id;
  const status = comment.status || "Open";
  if (!editorCommentStatusFilterValues.has(status)) {
    editorCommentStatusFilterValues.add(status);
  }
  if (editorCommentSearchQuery) {
    editorCommentSearchQuery = "";
    if (editorCommentSearchInput) editorCommentSearchInput.value = "";
  }
  if (options.ensurePanel !== false) {
    if (!workspaceAssistEnabled) {
      setWorkspaceAssistEnabled(true, { persist: true });
    } else {
      showWorkspaceAssistPanel();
    }
    setWorkspaceAssistTab("human");
  }
  renderEditorCommentList();
  window.setTimeout(() => {
    const card = [...(editorCommentList?.querySelectorAll("[data-comment-id]") || [])]
      .find((candidate) => candidate.dataset.commentId === id);
    card?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    focusPreviewCommentTarget(comment, { scroll: true });
    if (options.focusReply) focusEditorCommentReplyInput(id);
  }, 0);
}

function editorCommentReplies(comment = {}) {
  return Array.isArray(comment.replies) ? comment.replies.filter((reply) => reply?.note) : [];
}

function renderEditorCommentThread(comment = {}, active = false) {
  const replies = editorCommentReplies(comment);
  const replyList = replies.length
    ? `<div class="editor-comment-reply-list">
        ${replies.map((reply) => `
          <div class="editor-comment-reply">
            <small>${escapeHtml(editorCommentMetaLabel(reply))}</small>
            <p>${escapeHtml(reply.note || "")}</p>
          </div>
        `).join("")}
      </div>`
    : "";
  if (!active && !replyList) return "";
  return `
    <div class="editor-comment-thread">
      ${replyList}
      ${active
        ? `<div class="editor-comment-reply-composer">
            <textarea data-comment-reply-input rows="2" placeholder="답글을 입력해 주세요."></textarea>
            <button type="button" data-comment-reply-submit>답글 추가</button>
          </div>`
        : ""}
    </div>
  `;
}

function renderEditorAssistPanels() {
  renderSelectedElementPanel();
  renderEditorSuggestionList();
  renderEditorCommentList();
  updateEditorCommentComposer();
}

function renderSelectedElementPanel() {
  if (!selectedElementList) return;
  if (!selectedEditorContext) {
    selectedElementList.classList.add("empty");
    selectedElementList.innerHTML = "문단이나 표 셀을 선택하면 이 영역에서 바로 코멘트를 입력할 수 있습니다.";
    setAssistCount(selectedElementCount, 0);
    return;
  }
  selectedElementList.classList.remove("empty");
  setAssistCount(selectedElementCount, 1);
  const context = selectedEditorContext;
  const props = [
    ["위치", context.headingPath?.join(" > ") || "본문"],
    ["요소", context.kind || "문서 요소"],
    ["표 유형", context.tableType || "해당 없음"],
    ["추정 ID", context.elementId || "없음"],
    ["Trace", context.traceStatus || "DOM 기준 추정"],
  ];
  selectedElementList.innerHTML = `
    <div class="editor-context-card">
      <strong>${escapeHtml(context.title || "선택 요소")}</strong>
      <p>${escapeHtml(context.preview || "선택한 요소의 내용을 확인할 수 없습니다.")}</p>
      <dl>${props.map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>
    </div>
  `;
}

function renderEditorSuggestionList() {
  if (!editorSuggestionList) return;
  setAssistCount(editorSuggestionCount, editorSuggestions.length);
  if (!editorSuggestions.length) {
    editorSuggestionList.classList.add("empty");
    editorSuggestionList.innerHTML = "선택 영역에서 제안만 생성하면 여기에 모입니다.";
    return;
  }
  editorSuggestionList.classList.remove("empty");
  editorSuggestionList.innerHTML = editorSuggestions
    .map((item) => `
      <div class="editor-suggestion-item" data-suggestion-id="${escapeHtml(item.id)}">
        <span>${escapeHtml(item.status || "제안")}</span>
        <strong>${escapeHtml(item.headingPath?.join(" > ") || "선택 영역 제안")}</strong>
        <p>${escapeHtml(item.suggestionText || "")}</p>
        <em>${escapeHtml(item.instruction || "")}</em>
        <div class="editor-assist-actions">
          <button type="button" data-suggestion-action="apply">적용</button>
          <button type="button" data-suggestion-action="copy">수정 요청에 담기</button>
          <button type="button" data-suggestion-action="remove">닫기</button>
        </div>
      </div>
    `)
    .join("");
  editorSuggestionList.querySelectorAll("[data-suggestion-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest("[data-suggestion-id]");
      handleEditorSuggestionAction(card?.dataset.suggestionId || "", button.dataset.suggestionAction || "");
    });
  });
}

function renderEditorCommentList() {
  if (!editorCommentList) return;
  updateEditorCommentToolControls();
  const normalizedQuery = cleanWorkspaceText(editorCommentSearchQuery || "").toLowerCase();
  const activeStatuses = editorCommentStatusFilterValues;
  const allStatusesSelected = activeStatuses.size === EDITOR_COMMENT_STATUSES.length
    && EDITOR_COMMENT_STATUSES.every((status) => activeStatuses.has(status));
  const filteredComments = editorComments
    .filter((item) => activeStatuses.has(item.status || "Open"))
    .filter((item) => !normalizedQuery || editorCommentSearchText(item).includes(normalizedQuery))
    .slice()
    .sort(compareEditorCommentsByDate);
  const hasActiveFilter = Boolean(normalizedQuery) || !allStatusesSelected;
  setAssistCount(
    editorCommentCount,
    editorComments.length && hasActiveFilter ? `${filteredComments.length}/${editorComments.length}` : editorComments.length
  );
  if (!editorComments.length) {
    editorCommentList.classList.add("empty");
    editorCommentList.innerHTML = "코멘트를 Open/반영됨/보류로 관리합니다.";
    applyEditorCommentHighlights();
    return;
  }
  if (!filteredComments.length) {
    editorCommentList.classList.add("empty");
    editorCommentList.innerHTML = "검색·필터 조건에 맞는 코멘트가 없습니다.";
    applyEditorCommentHighlights();
    return;
  }
  editorCommentList.classList.remove("empty");
  editorCommentList.innerHTML = filteredComments
    .map((item) => `
      <div class="editor-comment-item ${escapeHtml(item.status || "Open")} ${item.id === selectedEditorCommentId ? "selected" : ""}" data-comment-id="${escapeHtml(item.id)}">
        <div class="editor-comment-item-head">
          <span class="editor-comment-status-chip">${escapeHtml(item.status || "Open")}</span>
          <details class="editor-comment-action-menu">
            <summary aria-label="코멘트 작업 메뉴"><span class="editor-comment-action-dots" aria-hidden="true"></span></summary>
            <div class="editor-comment-action-popover">
              <button type="button" data-comment-status="Open">Open</button>
              <button type="button" data-comment-status="반영됨">반영됨</button>
              <button type="button" data-comment-status="보류">보류</button>
              <button class="danger" type="button" data-comment-status="remove">삭제</button>
            </div>
          </details>
        </div>
        <small>${escapeHtml(editorCommentMetaLabel(item))}</small>
        <p>${escapeHtml(item.note || "")}</p>
        ${renderEditorCommentThread(item, item.id === selectedEditorCommentId)}
      </div>
    `)
    .join("");
  editorCommentList.querySelectorAll(".editor-comment-item").forEach((card) => {
    card.addEventListener("click", (event) => {
      if (event.target.closest(".editor-comment-action-menu, [data-comment-reply-input], [data-comment-reply-submit]")) return;
      selectEditorComment(card.dataset.commentId || "", { focusReply: true, ensurePanel: false });
    });
  });
  editorCommentList.querySelectorAll(".editor-comment-action-menu").forEach((menu) => {
    menu.addEventListener("toggle", () => {
      if (menu.open) closeEditorCommentActionMenus(menu);
    });
  });
  editorCommentList.querySelectorAll("[data-comment-status]").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest("[data-comment-id]");
      const menu = button.closest("details");
      if (menu) menu.open = false;
      updateEditorCommentStatus(card?.dataset.commentId || "", button.dataset.commentStatus || "Open");
    });
  });
  editorCommentList.querySelectorAll("[data-comment-reply-submit]").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest("[data-comment-id]");
      submitEditorCommentReply(card?.dataset.commentId || "");
    });
  });
  editorCommentList.querySelectorAll("[data-comment-reply-input]").forEach((input) => {
    input.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        const card = input.closest("[data-comment-id]");
        submitEditorCommentReply(card?.dataset.commentId || "");
      }
    });
  });
  applyEditorCommentHighlights();
}

function editorAssistId(prefix) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function currentEditorCommentAuthor() {
  return cleanWorkspaceText(currentUser?.name || document.querySelector("#author")?.value || "Policy Web") || "Policy Web";
}

function editorCommentMetaLabel(comment = {}) {
  const author = cleanWorkspaceText(comment.author || comment.authorName || "작성자 미상") || "작성자 미상";
  const createdAt = formatDate(comment.createdAt || comment.updatedAt || "");
  return `${author} · ${createdAt}`;
}

function hasEditorCommentDocument() {
  return Boolean(selectedName || selectedDraft);
}

function buildDocumentCommentContext() {
  const item = selectedPolicyItem();
  const title = selectedDraft?.topic || item?.title || item?.topic || selectedName || "문서";
  return {
    kind: "문서",
    title: "문서 전체",
    preview: title,
    headingPath: ["문서 전체"],
    traceStatus: "문서 기준",
  };
}

function currentEditorCommentContext(options = {}) {
  return options.allowSelectedArea && selectedRevisionTarget
    ? selectedRevisionTarget
    : buildDocumentCommentContext();
}

function editorCommentContextLabel(context = currentEditorCommentContext()) {
  if (!hasEditorCommentDocument()) return "문서를 선택하면 코멘트를 남길 수 있습니다.";
  if (isDocumentLevelComment(context)) return "문서 전체";
  const path = context?.headingPath?.filter(Boolean).join(" > ");
  const target = path || context?.title || "문서 전체";
  const preview = limitClientText(context?.preview || context?.text || context?.blockText || "", 72);
  return `${target}${preview ? ` · ${preview}` : ""}`;
}

function editorCommentTargetKey(context = null) {
  const elementId = cleanWorkspaceText(context?.elementId || "").toUpperCase();
  const headingPath = Array.isArray(context?.headingPath)
    ? context.headingPath.map((item) => cleanWorkspaceText(item)).filter(Boolean).join(">")
    : "";
  const tableType = cleanWorkspaceText(context?.tableType || "");
  const kind = cleanWorkspaceText(context?.kind || "");
  const preview = cleanWorkspaceText(context?.preview || context?.targetText || context?.blockText || context?.text || "").slice(0, 220);
  return [elementId, headingPath, tableType, kind, preview].join("|");
}

function previewCommentMarkerToneClass(status = "Open") {
  return status === "보류" ? "nc-preview-comment-marker-hold" : "nc-preview-comment-marker-open";
}

function previewCommentMarkerStatus(comments = []) {
  return comments.some((comment) => comment.status === "보류") ? "보류" : "Open";
}

function previewCommentMarkerStatusLabel(status = "Open") {
  return status === "보류" ? "보류 코멘트" : "Open 코멘트";
}

function isDocumentLevelComment(comment = null) {
  const kind = cleanWorkspaceText(comment?.targetKind || comment?.kind || "");
  const headingPath = Array.isArray(comment?.headingPath)
    ? comment.headingPath.map((item) => cleanWorkspaceText(item)).filter(Boolean)
    : [];
  return kind === "문서" || (headingPath.length === 1 && headingPath[0] === "문서 전체");
}

function clearEditorCommentHighlights(doc = null) {
  let targetDoc = doc;
  if (!targetDoc) {
    try {
      targetDoc = previewFrame?.contentDocument;
    } catch (_error) {
      return;
    }
  }
  if (!targetDoc?.body) return;
  targetDoc.querySelectorAll(`[data-nc-preview-comment-marker], .${PREVIEW_COMMENT_MARKER_CLASS}`).forEach((element) => {
    element.remove();
  });
  targetDoc.querySelectorAll(`.${PREVIEW_COMMENT_HIGHLIGHT_CLASS}`).forEach((element) => {
    element.classList.remove(
      PREVIEW_COMMENT_HIGHLIGHT_CLASS,
      PREVIEW_COMMENT_SELECTED_CLASS,
      "nc-preview-comment-open",
      "nc-preview-comment-hold",
      "nc-preview-comment-resolved"
    );
    element.removeAttribute("data-nc-comment-count");
    element.removeAttribute("data-nc-comment-title");
    element.removeAttribute("data-nc-comment-latest");
    element.removeAttribute("data-nc-selected-comment");
  });
  targetDoc.querySelectorAll(`.${PREVIEW_COMMENT_ANCHOR_CLASS}`).forEach((element) => {
    element.classList.remove(
      PREVIEW_COMMENT_ANCHOR_CLASS,
      "nc-preview-comment-open-anchor",
      "nc-preview-comment-hold-anchor"
    );
    element.removeAttribute("data-nc-comment-count");
    element.removeAttribute("data-nc-comment-title");
    element.removeAttribute("data-nc-comment-latest");
    element.removeAttribute("data-nc-comment-marker-for");
  });
}

function previewDocumentForCommentFocus() {
  try {
    return previewFrame?.contentDocument || null;
  } catch (_error) {
    return null;
  }
}

function previewCommentHighlightCandidates(doc) {
  if (!doc?.body) return [];
  const candidates = [];
  const seen = new Set();
  doc.body.querySelectorAll("tr, p, li, h1, h2, h3, h4, .diagram-wrap").forEach((block) => {
    if (!block || seen.has(block)) return;
    seen.add(block);
    candidates.push(block);
  });
  return candidates;
}

function findEditorCommentTargetBlock(doc, comment) {
  if (isDocumentLevelComment(comment)) return null;
  const candidates = previewCommentHighlightCandidates(doc);
  if (!candidates.length) return null;
  const commentKey = cleanWorkspaceText(comment?.targetKey || "");
  if (commentKey) {
    const keyMatch = candidates.find((candidate) => {
      const context = buildSelectedEditorContext(doc, candidate);
      return context && editorCommentTargetKey(context) === commentKey;
    });
    if (keyMatch) return keyMatch;
  }

  const elementId = cleanWorkspaceText(comment?.elementId || "").toUpperCase();
  if (elementId) {
    const idMatch = candidates.find((candidate) =>
      cleanWorkspaceText(candidate.textContent || "").toUpperCase().includes(elementId)
    );
    if (idMatch) return idMatch;
  }

  const targetText = cleanWorkspaceText(comment?.targetText || comment?.preview || "");
  if (targetText.length >= 8) {
    const textMatch = candidates.find((candidate) =>
      cleanWorkspaceText(candidate.textContent || "").includes(targetText)
    );
    if (textMatch) return textMatch;
    const shortTarget = targetText.slice(0, 80);
    if (shortTarget.length >= 20) {
      const shortMatch = candidates.find((candidate) =>
        cleanWorkspaceText(candidate.textContent || "").includes(shortTarget)
      );
      if (shortMatch) return shortMatch;
    }
    const targetFragments = targetText
      .split(/[\n\r\t|·•,.;:()\[\]{}]+/)
      .map((item) => cleanWorkspaceText(item))
      .filter((item) => item.length >= 8 && item.length <= 120)
      .sort((a, b) => b.length - a.length);
    for (const fragment of targetFragments.slice(0, 12)) {
      const fragmentMatch = candidates.find((candidate) =>
        cleanWorkspaceText(candidate.textContent || "").includes(fragment)
      );
      if (fragmentMatch) return fragmentMatch;
    }
  }

  const blockText = cleanWorkspaceText(comment?.blockText || "");
  if (blockText.length >= 8) {
    const blockMatch = candidates.find((candidate) =>
      cleanWorkspaceText(candidate.textContent || "").includes(blockText)
    );
    if (blockMatch) return blockMatch;
    const blockShort = blockText.slice(0, 100);
    if (blockShort.length >= 20) {
      const blockShortMatch = candidates.find((candidate) =>
        cleanWorkspaceText(candidate.textContent || "").includes(blockShort)
      );
      if (blockShortMatch) return blockShortMatch;
    }
  }

  const headingPath = Array.isArray(comment?.headingPath)
    ? comment.headingPath.map((item) => cleanWorkspaceText(item)).filter(Boolean)
    : [];
  if (headingPath.length) {
    const headingLabel = headingPath[headingPath.length - 1];
    const headingMatch = candidates.find((candidate) =>
      cleanWorkspaceText(candidate.textContent || "").includes(headingLabel)
    );
    if (headingMatch) return headingMatch;
  }

  return null;
}

function applySelectedPreviewCommentHighlight(doc, comment) {
  if (!doc?.body || !comment) return null;
  const block = findEditorCommentTargetBlock(doc, comment);
  if (!block) return null;
  block.classList.add(PREVIEW_COMMENT_HIGHLIGHT_CLASS, PREVIEW_COMMENT_SELECTED_CLASS);
  block.setAttribute("data-nc-selected-comment", comment.id || "");
  return block;
}

function focusPreviewCommentTarget(comment, options = {}) {
  const doc = previewDocumentForCommentFocus();
  if (!doc?.body || !comment) return false;
  const block = applySelectedPreviewCommentHighlight(doc, comment);
  if (!block) return false;
  if (options.scroll) {
    try {
      block.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
      previewFrame?.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
    } catch (_error) {
      block.scrollIntoView();
    }
  }
  return true;
}

function applyEditorCommentHighlights() {
  let doc;
  try {
    doc = previewFrame?.contentDocument;
  } catch (_error) {
    return;
  }
  if (!doc?.body) return;
  clearEditorCommentHighlights(doc);
  const activeSelectedComment = selectedEditorCommentId
    ? editorComments.find((comment) => comment.id === selectedEditorCommentId)
    : null;
  applySelectedPreviewCommentHighlight(doc, activeSelectedComment);
  const grouped = new Map();
  editorComments
    .filter((comment) => ["Open", "보류"].includes(comment.status || "Open"))
    .forEach((comment) => {
      const block = findEditorCommentTargetBlock(doc, comment);
      if (!block) return;
      const comments = grouped.get(block) || [];
      comments.push(comment);
      grouped.set(block, comments);
    });
  grouped.forEach((comments, block) => {
    const sortedComments = comments.slice().sort(compareEditorCommentsRecentFirst);
    const markerComment = sortedComments[0];
    const selectedMarkerComment = selectedEditorCommentId
      ? sortedComments.find((comment) => comment.id === selectedEditorCommentId)
      : null;
    const markerStatus = previewCommentMarkerStatus(sortedComments);
    const markerStatusLabel = previewCommentMarkerStatusLabel(markerStatus);
    const anchor = previewCommentMarkerAnchor(block);
    if (!anchor || !markerComment) return;
    const count = sortedComments.length;
    anchor.classList.add(PREVIEW_COMMENT_ANCHOR_CLASS);
    anchor.classList.toggle("nc-preview-comment-hold-anchor", markerStatus === "보류");
    anchor.classList.toggle("nc-preview-comment-open-anchor", markerStatus !== "보류");
    anchor.setAttribute("data-nc-comment-count", String(count));
    anchor.setAttribute("data-nc-comment-title", `${markerStatusLabel} ${count}건`);
    anchor.setAttribute("data-nc-comment-marker-for", markerComment.id || "");
    const marker = doc.createElement("button");
    marker.type = "button";
    marker.className = `${PREVIEW_COMMENT_MARKER_CLASS} ${previewCommentMarkerToneClass(markerStatus)}`;
    marker.setAttribute("data-nc-preview-comment-marker", "true");
    marker.setAttribute("data-comment-id", markerComment.id || "");
    marker.setAttribute("data-comment-status", markerStatus);
    marker.setAttribute("aria-label", `${markerStatusLabel} ${count}건 보기`);
    marker.title = `${markerStatusLabel} ${count}건`;
    marker.textContent = count > 1 ? String(count) : "";
    marker.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      selectEditorComment(marker.dataset.commentId || "");
    });
    anchor.appendChild(marker);
    if (selectedMarkerComment) {
      applySelectedPreviewCommentHighlight(doc, selectedMarkerComment);
      marker.classList.add("nc-preview-comment-marker-selected");
    }
  });
}

function previewCommentMarkerAnchor(block) {
  if (!block) return null;
  if (block.tagName === "TR") {
    return [...block.children].reverse().find((cell) => ["TD", "TH"].includes(cell.tagName)) || null;
  }
  return block;
}

function updateEditorCommentComposer() {
  const hasDocument = hasEditorCommentDocument();
  if (editorCommentStickyPanel) {
    editorCommentStickyPanel.hidden = !hasDocument;
  }
  if (editorCommentComposer && editorCommentComposerSlot && editorCommentComposer.parentElement !== editorCommentComposerSlot) {
    editorCommentComposerSlot.appendChild(editorCommentComposer);
  }
  if (editorCommentComposer) {
    editorCommentComposer.setAttribute("aria-disabled", String(!hasDocument));
  }
  if (editorCommentTarget) {
    editorCommentTarget.textContent = hasDocument
      ? `대상: ${editorCommentContextLabel()}`
      : "문서를 선택하면 코멘트를 남길 수 있습니다.";
  }
  if (editorCommentInput) {
    editorCommentInput.disabled = !hasDocument;
    editorCommentInput.placeholder = hasDocument
      ? "검토 코멘트를 입력해 주세요. Ctrl/⌘+Enter로 추가할 수 있습니다."
      : "문서를 선택하면 코멘트를 남길 수 있습니다.";
  }
  if (editorCommentSubmitButton) {
    editorCommentSubmitButton.disabled = !hasDocument;
  }
}

function focusEditorCommentComposer() {
  if (!selectedName && !selectedDraft) {
    setMessage("코멘트를 남길 문서를 먼저 선택해 주세요.", true);
    return;
  }
  if (!workspaceAssistEnabled) {
    setWorkspaceAssistEnabled(true, { persist: true });
  } else {
    showWorkspaceAssistPanel();
  }
  setWorkspaceAssistTab("human");
  updateEditorCommentComposer();
  editorCommentInput?.focus();
}

async function submitEditorComment() {
  if (!hasEditorCommentDocument()) {
    setMessage("코멘트를 남길 문서를 먼저 선택해 주세요.", true);
    return;
  }
  const note = String(editorCommentInput?.value || "").trim();
  if (!note) {
    editorCommentInput?.focus();
    setMessage("검토 코멘트를 입력해 주세요.", true);
    return;
  }
  await addEditorCommentFromCurrentContext(note);
  if (editorCommentInput) editorCommentInput.value = "";
  updateEditorCommentComposer();
}

async function addEditorCommentFromCurrentContext(note = "", options = {}) {
  const commentText = String(note || "").trim();
  if (!commentText) {
    focusEditorCommentComposer();
    return;
  }
  if (!hasEditorCommentDocument()) {
    setMessage("코멘트를 남길 문서를 먼저 선택해 주세요.", true);
    return;
  }
  const context = currentEditorCommentContext(options);
  const now = new Date().toISOString();
  const comment = {
    id: editorAssistId("comment"),
    targetText: limitClientText(context.preview || context.text || context.blockText || "", 260),
    blockText: limitClientText(context.blockText || context.preview || context.text || "", 500),
    headingPath: context.headingPath || [],
    targetKey: context.targetKey || editorCommentTargetKey(context),
    elementId: context.elementId || "",
    tableType: context.tableType || "",
    targetKind: context.kind || "",
    note: commentText,
    status: "Open",
    author: currentEditorCommentAuthor(),
    createdAt: now,
    updatedAt: now,
  };
  editorComments.unshift(comment);
  selectedEditorCommentId = "";
  saveEditorComments();
  renderEditorCommentList();
  setMessage("검토 코멘트를 Co-work 패널에 추가했습니다.");
  if (editorCommentsUseServer()) {
    try {
      await persistEditorCommentAction("add", { comment });
      setMessage("공동 코멘트를 저장했습니다.");
    } catch (error) {
      handleEditorCommentSyncError(error);
    }
  }
}

async function updateEditorCommentStatus(id, status) {
  if (!id) return;
  if (status === "remove") {
    editorComments = editorComments.filter((item) => item.id !== id);
    if (selectedEditorCommentId === id) selectedEditorCommentId = "";
  } else {
    editorComments = editorComments.map((item) =>
      item.id === id ? { ...item, status, updatedAt: new Date().toISOString() } : item
    );
  }
  saveEditorComments();
  renderEditorCommentList();
  if (editorCommentsUseServer()) {
    try {
      await persistEditorCommentAction(status === "remove" ? "delete" : "status", {
        id,
        status: status === "remove" ? undefined : status,
      });
    } catch (error) {
      handleEditorCommentSyncError(error);
      refreshSharedEditorComments();
    }
  }
}

function submitEditorCommentReply(commentId = "") {
  if (!commentId) return;
  const card = [...(editorCommentList?.querySelectorAll("[data-comment-id]") || [])]
    .find((candidate) => candidate.dataset.commentId === commentId);
  const input = card?.querySelector("[data-comment-reply-input]");
  const note = String(input?.value || "").trim();
  if (!note) {
    input?.focus();
    setMessage("답글 내용을 입력해 주세요.", true);
    return;
  }
  addEditorCommentReply(commentId, note);
}

async function addEditorCommentReply(commentId = "", note = "") {
  const replyText = String(note || "").trim();
  if (!commentId || !replyText) return;
  const now = new Date().toISOString();
  let added = false;
  const reply = {
    id: editorAssistId("reply"),
    note: replyText,
    author: currentEditorCommentAuthor(),
    createdAt: now,
    updatedAt: now,
  };
  editorComments = editorComments.map((comment) => {
    if (comment.id !== commentId) return comment;
    added = true;
    const replies = editorCommentReplies(comment);
    return {
      ...comment,
      replies: [
        ...replies,
        reply,
      ],
      updatedAt: now,
    };
  });
  if (!added) return;
  saveEditorComments();
  renderEditorCommentList();
  focusEditorCommentReplyInput(selectedEditorCommentId);
  setMessage("코멘트 스레드에 답글을 추가했습니다.");
  if (editorCommentsUseServer()) {
    try {
      await persistEditorCommentAction("reply", { id: commentId, reply });
      setMessage("코멘트 스레드에 답글을 저장했습니다.");
    } catch (error) {
      handleEditorCommentSyncError(error);
      refreshSharedEditorComments();
    }
  }
}

function createEditorSuggestion(instruction, target) {
  const suggestionText = buildClientSuggestionText(target, instruction);
  editorSuggestions.unshift({
    id: editorAssistId("suggestion"),
    targetText: target.text,
    blockText: target.blockText,
    headingPath: target.headingPath || [],
    instruction,
    suggestionText,
    status: "제안",
    createdAt: new Date().toISOString(),
  });
  saveEditorSuggestions();
  renderEditorSuggestionList();
}

function buildClientSuggestionText(target, instruction) {
  const base = cleanWorkspaceText(target.text || target.blockText || "");
  const trimmedInstruction = cleanWorkspaceText(instruction);
  if (!base) return trimmedInstruction;
  return `${base}\n\n[보완 제안] ${trimmedInstruction}`;
}

function handleEditorSuggestionAction(id, action) {
  const item = editorSuggestions.find((candidate) => candidate.id === id);
  if (!item) return;
  if (action === "remove") {
    editorSuggestions = editorSuggestions.filter((candidate) => candidate.id !== id);
    saveEditorSuggestions();
    renderEditorSuggestionList();
    return;
  }
  if (action === "copy") {
    if (revisionRequest) {
      revisionRequest.value = item.instruction || item.suggestionText || "";
      revisionRequest.focus();
    }
    setMessage("AI 제안 내용을 수정 요청 메모에 담았습니다.");
    return;
  }
  if (action === "apply") {
    applyEditorSuggestion(item);
  }
}

function applyEditorSuggestion(item) {
  if (!isEditing || !previewFrame?.contentDocument) {
    setMessage("AI 제안 적용은 직접 편집 모드에서만 가능합니다.", true);
    return;
  }
  const applied = replaceTextInPreviewDocument(item.targetText, item.suggestionText);
  if (!applied) {
    setMessage("선택했던 문장을 현재 문서에서 찾지 못했습니다. 제안을 수정 요청 메모에 담아 다시 적용해 주세요.", true);
    return;
  }
  editorSuggestions = editorSuggestions.map((candidate) =>
    candidate.id === item.id ? { ...candidate, status: "적용됨" } : candidate
  );
  saveEditorSuggestions();
  renderEditorSuggestionList();
  setMessage("AI 제안을 현재 편집 문서에 적용했습니다. 최종 반영은 '저장 검토'에서 확인해 주세요.");
}

function replaceTextInPreviewDocument(targetText, replacementText) {
  const cleanTarget = cleanWorkspaceText(targetText);
  if (!cleanTarget || !replacementText) return false;
  const doc = previewFrame.contentDocument;
  const nodeFilter = doc.defaultView?.NodeFilter?.SHOW_TEXT || 4;
  const walker = doc.createTreeWalker(doc.body, nodeFilter);
  let node;
  while ((node = walker.nextNode())) {
    const nodeText = cleanWorkspaceText(node.nodeValue || "");
    if (!nodeText || !nodeText.includes(cleanTarget)) continue;
    const original = String(node.nodeValue || "");
    node.nodeValue = original.replace(targetText, replacementText);
    if (node.nodeValue === original) {
      node.nodeValue = replacementText;
    }
    return true;
  }
  return false;
}

function nextElementByTag(element, tagName) {
  let node = element.nextElementSibling;
  while (node) {
    if (node.tagName === tagName) return node;
    node = node.nextElementSibling;
  }
  return null;
}

function classifyPolicyValue(text) {
  if (/인증|본인|PASS|동의/.test(text)) return "인증";
  if (/횟수|회\b|재시도/.test(text)) return "횟수";
  if (/유효시간|시간|기간|일\b|개월|년/.test(text)) return "시간";
  if (/채널|앱|웹|SMS|이메일|푸시/.test(text)) return "채널";
  if (/저장|이력|로그|보관|파기/.test(text)) return "이력";
  if (/제한|불가|금지|마스킹/.test(text)) return "제한";
  if (/BSS|판정|식별자|CI|DI/.test(text)) return "판정";
  return "정책값";
}

function cleanWorkspaceText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function resetPreviewFrameHeight() {
  if (!previewFrame) return;
  previewFrame.style.height = "";
}

function resizePreviewFrameToContent() {
  if (!previewFrame) return;
  let doc;
  try {
    doc = previewFrame.contentDocument;
  } catch (error) {
    resetPreviewFrameHeight();
    return;
  }
  if (!doc || !isAnalysisReferencePreviewDocument(doc)) {
    resetPreviewFrameHeight();
    return;
  }
  const body = doc.body;
  const html = doc.documentElement;
  const height = Math.max(
    body?.scrollHeight || 0,
    body?.offsetHeight || 0,
    html?.clientHeight || 0,
    html?.scrollHeight || 0,
    html?.offsetHeight || 0
  );
  if (height > 0) {
    const extraHeight = isFeatureInventoryPreviewDocument(doc) ? 36 : 160;
    previewFrame.style.height = `${Math.ceil(height + extraHeight)}px`;
  }
}

function isAnalysisReferencePreviewDocument(doc) {
  const framePath = doc?.location?.pathname || "";
  return /\/output\/reference_html\/(?!tk-task-\d+\.html)/.test(framePath);
}

function isFeatureInventoryPreviewDocument(doc) {
  const framePath = doc?.location?.pathname || "";
  return /\/output\/reference_html\/function-inventory-[^/]+\.html$/.test(framePath);
}

function hidePreviewFrameScrollbars() {
  let doc;
  try {
    doc = previewFrame?.contentDocument;
  } catch (error) {
    return;
  }
  const isAnalysisReferencePreview = isAnalysisReferencePreviewDocument(doc);
  if (!doc || doc.__ncScrollbarHidden || !isAnalysisReferencePreview) return;
  const isFeatureInventoryPreview = isFeatureInventoryPreviewDocument(doc);
  const previewPageRule = isAnalysisReferencePreview
    ? `
    .page {
      width: calc(100% - 24px) !important;
      max-width: none !important;
      margin: 0 auto !important;
      padding: ${isFeatureInventoryPreview ? "20px 0 56px" : "20px 0 144px"} !important;
      box-sizing: border-box !important;
    }
    @media (max-width: 720px) {
      .page {
        width: calc(100% - 20px) !important;
        padding: ${isFeatureInventoryPreview ? "14px 0 48px" : "14px 0 112px"} !important;
      }
    }
    `
    : `
    .page {
      width: min(1480px, calc(100vw - 40px)) !important;
      max-width: 1480px !important;
      margin: 24px auto !important;
      padding-left: 42px !important;
      padding-right: 42px !important;
      box-sizing: border-box !important;
    }
    `;
  const style = doc.createElement("style");
  style.setAttribute("data-nc-preview-scrollbar", "hidden");
  style.setAttribute("data-nc-preview-style", "true");
  style.textContent = `
    html, body {
      scrollbar-width: none !important;
      -ms-overflow-style: none !important;
    }
    ${previewPageRule}
	    table {
	      width: 100% !important;
	      max-width: 100% !important;
	      table-layout: auto !important;
	    }
	    .nc-preview-usecase-table,
	    .nc-preview-state-code-table,
	    .nc-preview-state-transition-table,
	    .nc-preview-process-table,
	    .nc-preview-function-table,
	    .nc-preview-policy-table {
	      table-layout: fixed !important;
	    }
	    .nc-preview-usecase-table th:nth-child(1), .nc-preview-usecase-table td:nth-child(1) { width: 15% !important; }
	    .nc-preview-usecase-table th:nth-child(2), .nc-preview-usecase-table td:nth-child(2) { width: 13% !important; }
	    .nc-preview-usecase-table th:nth-child(3), .nc-preview-usecase-table td:nth-child(3) { width: 19% !important; }
	    .nc-preview-usecase-table th:nth-child(4), .nc-preview-usecase-table td:nth-child(4) { width: 38% !important; }
	    .nc-preview-usecase-table th:nth-child(5), .nc-preview-usecase-table td:nth-child(5) { width: 15% !important; }
	    .nc-preview-state-code-table th:nth-child(1), .nc-preview-state-code-table td:nth-child(1) { width: 16% !important; }
	    .nc-preview-state-code-table th:nth-child(2), .nc-preview-state-code-table td:nth-child(2) { width: 16% !important; }
	    .nc-preview-state-code-table th:nth-child(3), .nc-preview-state-code-table td:nth-child(3) { width: 42% !important; }
	    .nc-preview-state-code-table th:nth-child(4), .nc-preview-state-code-table td:nth-child(4) { width: 26% !important; }
	    .nc-preview-state-transition-table th:nth-child(1), .nc-preview-state-transition-table td:nth-child(1) { width: 16% !important; }
	    .nc-preview-state-transition-table th:nth-child(2), .nc-preview-state-transition-table td:nth-child(2) { width: 22% !important; }
	    .nc-preview-state-transition-table th:nth-child(3), .nc-preview-state-transition-table td:nth-child(3) { width: 16% !important; }
	    .nc-preview-state-transition-table th:nth-child(4), .nc-preview-state-transition-table td:nth-child(4) { width: 46% !important; }
	    .nc-preview-process-table th:nth-child(1), .nc-preview-process-table td:nth-child(1) { width: 16% !important; }
	    .nc-preview-process-table th:nth-child(2), .nc-preview-process-table td:nth-child(2) { width: 18% !important; }
	    .nc-preview-process-table th:nth-child(3), .nc-preview-process-table td:nth-child(3) { width: 25% !important; }
	    .nc-preview-process-table th:nth-child(4), .nc-preview-process-table td:nth-child(4) { width: 22% !important; }
	    .nc-preview-process-table th:nth-child(5), .nc-preview-process-table td:nth-child(5) { width: 19% !important; }
	    .nc-preview-function-table th:nth-child(1), .nc-preview-function-table td:nth-child(1),
	    .nc-preview-policy-table th:nth-child(1), .nc-preview-policy-table td:nth-child(1) { width: 16% !important; }
	    .nc-preview-function-table th:nth-child(2), .nc-preview-function-table td:nth-child(2),
	    .nc-preview-policy-table th:nth-child(2), .nc-preview-policy-table td:nth-child(2) { width: 18% !important; }
	    .nc-preview-function-table th:nth-child(3), .nc-preview-function-table td:nth-child(3),
	    .nc-preview-policy-table th:nth-child(3), .nc-preview-policy-table td:nth-child(3) { width: 32% !important; }
	    .nc-preview-function-table th:nth-child(4), .nc-preview-function-table td:nth-child(4),
	    .nc-preview-policy-table th:nth-child(4), .nc-preview-policy-table td:nth-child(4) { width: 34% !important; }
	    th,
	    td {
	      overflow-wrap: anywhere !important;
	      word-break: normal !important;
	    }
    .mono {
      word-break: break-word !important;
    }
    .diagram-wrap {
      display: block !important;
      overflow-x: hidden !important;
      text-align: left !important;
    }
    .diagram-wrap pre.mermaid,
    .diagram-wrap .mermaid {
      display: none !important;
    }
    .nc-preview-diagram-static {
      display: grid;
      gap: 14px;
      width: 100%;
      box-sizing: border-box;
      color: #1f2937;
    }
    .nc-preview-diagram-note {
      display: inline-flex;
      width: fit-content;
      align-items: center;
      border: 1px solid #bfdbfe;
      border-radius: 999px;
      background: #eff6ff;
      color: #1d4ed8;
      font-size: 12px;
      font-weight: 800;
      padding: 5px 10px;
    }
    .nc-preview-diagram-nodes,
    .nc-preview-diagram-edges {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .nc-preview-diagram-node {
      border: 1px solid #dbeafe;
      border-radius: 14px;
      background: #f8fbff;
      color: #111827;
      font-size: 12px;
      font-weight: 800;
      line-height: 1.45;
      padding: 8px 10px;
    }
    .nc-preview-diagram-edge {
      flex: 1 1 260px;
      border: 1px solid #e5e7eb;
      border-radius: 14px;
      background: #fff;
      color: #374151;
      font-size: 12px;
      line-height: 1.5;
      padding: 8px 10px;
    }
    .nc-preview-diagram-edge strong {
      color: #111827;
      font-weight: 900;
    }
    .nc-preview-diagram-empty {
      border: 1px dashed #cbd5e1;
      border-radius: 14px;
      background: #f8fafc;
      color: #475569;
      font-size: 12px;
      line-height: 1.6;
      padding: 12px;
    }
	    .nc-preview-comment-anchor {
	      position: relative !important;
	    }
	    .nc-preview-comment-highlight {
	      background:
	        linear-gradient(transparent 18%, rgba(250, 204, 21, 0.36) 18%, rgba(250, 204, 21, 0.36) 86%, transparent 86%) !important;
	      border-radius: 6px !important;
	      box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.2) !important;
	      transition: background 0.16s ease, box-shadow 0.16s ease !important;
	    }
	    tr.nc-preview-comment-highlight,
	    tr.nc-preview-comment-highlight > th,
	    tr.nc-preview-comment-highlight > td {
	      background: rgba(254, 240, 138, 0.55) !important;
	    }
	    .nc-preview-comment-selected {
	      outline: 2px solid rgba(245, 158, 11, 0.42) !important;
	      outline-offset: 3px !important;
	    }
	    .nc-preview-comment-marker {
	      position: absolute;
      top: 50%;
      right: -25px;
      z-index: 40;
      display: grid;
      width: 18px;
      min-width: 18px;
      height: 18px;
      place-items: center;
      border: 1px solid #fff;
      border-radius: 999px;
      background: #2563eb;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.18);
      color: #fff;
      cursor: pointer;
      font-size: 10px;
      font-weight: 900;
      line-height: 1;
      transform: translateY(-50%);
      transition: transform 0.14s ease, box-shadow 0.14s ease, background 0.14s ease;
    }
    .nc-preview-comment-marker::before {
      content: "";
      display: block;
      width: 8px;
      height: 6px;
      border: 2px solid currentColor;
      border-radius: 5px;
      box-sizing: border-box;
    }
    .nc-preview-comment-marker::after {
      content: "";
      position: absolute;
      right: 4px;
      bottom: 3px;
      width: 4px;
      height: 4px;
      border-right: 2px solid currentColor;
      border-bottom: 2px solid currentColor;
      transform: skew(-25deg);
    }
    .nc-preview-comment-marker:not(:empty)::before,
    .nc-preview-comment-marker:not(:empty)::after {
      content: none;
    }
    .nc-preview-comment-marker:hover,
    .nc-preview-comment-marker:focus-visible {
      box-shadow: 0 6px 16px rgba(15, 23, 42, 0.22);
      outline: 2px solid rgba(49, 130, 246, 0.24);
      outline-offset: 2px;
      transform: translateY(-50%) scale(1.08);
    }
    .nc-preview-comment-marker-open {
      background: #2563eb;
    }
    .nc-preview-comment-marker-hold {
      background: #f59e0b;
      color: #3b2500;
    }
	    .nc-preview-comment-marker-hold:hover,
	    .nc-preview-comment-marker-hold:focus-visible {
	      outline-color: rgba(245, 158, 11, 0.3);
	    }
	    .nc-preview-comment-marker-selected {
	      outline: 3px solid rgba(245, 158, 11, 0.38);
	      outline-offset: 2px;
	      transform: translateY(-50%) scale(1.12);
	    }
	    td.nc-preview-comment-anchor .nc-preview-comment-marker,
    th.nc-preview-comment-anchor .nc-preview-comment-marker {
      right: -22px;
    }
    .nc-preview-version-change-highlight {
      position: relative !important;
      outline: 2px solid rgba(37, 99, 235, 0.24) !important;
      outline-offset: 2px !important;
      border-radius: 8px !important;
      transition: outline-color 0.16s ease, box-shadow 0.16s ease, background 0.16s ease !important;
    }
    .nc-preview-version-change-added {
      background: rgba(209, 250, 229, 0.58) !important;
      outline-color: rgba(16, 185, 129, 0.36) !important;
    }
    .nc-preview-version-change-changed {
      background: rgba(219, 234, 254, 0.58) !important;
      outline-color: rgba(37, 99, 235, 0.34) !important;
    }
    tr.nc-preview-version-change-added > th,
    tr.nc-preview-version-change-added > td {
      background: rgba(209, 250, 229, 0.58) !important;
    }
    tr.nc-preview-version-change-changed > th,
    tr.nc-preview-version-change-changed > td {
      background: rgba(219, 234, 254, 0.58) !important;
    }
    .nc-preview-version-change-active {
      outline-width: 3px !important;
      outline-color: rgba(15, 23, 42, 0.58) !important;
      box-shadow: 0 0 0 6px rgba(37, 99, 235, 0.12) !important;
    }
    .nc-preview-version-change-badge-host {
      position: relative !important;
    }
    .nc-preview-version-change-badge {
      position: absolute;
      top: 6px;
      right: 6px;
      z-index: 52;
      display: inline-flex;
      min-width: 34px;
      height: 22px;
      align-items: center;
      justify-content: center;
      border: 1px solid rgba(255, 255, 255, 0.88);
      border-radius: 999px;
      background: #2563eb;
      box-shadow: 0 8px 18px rgba(15, 23, 42, 0.18);
      color: #fff;
      cursor: pointer;
      font-size: 10px;
      font-weight: 950;
      letter-spacing: 0;
      padding: 0 8px;
    }
    .nc-preview-version-change-badge.nc-preview-version-change-added {
      background: #059669;
    }
    .nc-preview-version-change-badge.nc-preview-version-change-changed {
      background: #2563eb;
    }
    .nc-preview-version-change-badge:hover,
    .nc-preview-version-change-badge:focus-visible {
      outline: 2px solid rgba(15, 23, 42, 0.2);
      outline-offset: 2px;
    }
    html::-webkit-scrollbar,
    body::-webkit-scrollbar,
    *::-webkit-scrollbar {
      width: 0 !important;
      height: 0 !important;
      display: none !important;
    }
  `;
  (doc.head || doc.documentElement).appendChild(style);
  doc.__ncScrollbarHidden = true;
}

function applyResponsivePreviewLayout(doc) {
  if (!doc || doc.__ncResponsivePreviewLayout) return;
  if (isAnalysisReferencePreviewDocument(doc)) return;
  const style = doc.createElement("style");
  style.setAttribute("data-nc-preview-responsive", "true");
  style.textContent = `
    html, body {
      max-width: 100%;
      overflow-x: hidden !important;
    }
    body {
      margin: 0 !important;
    }
    .page {
      width: min(1480px, calc(100% - 32px)) !important;
      max-width: calc(100% - 32px) !important;
      margin: 0 auto 28px !important;
      box-sizing: border-box !important;
    }
    @media (max-width: 900px) {
      .page {
        width: calc(100% - 18px) !important;
        max-width: calc(100% - 18px) !important;
      }
    }
    table,
    img,
    svg,
    canvas,
    video,
    pre {
      max-width: 100% !important;
    }
    table {
      width: 100% !important;
    }
    th,
    td,
    .mono {
      overflow-wrap: anywhere !important;
      word-break: normal !important;
    }
  `;
  (doc.head || doc.documentElement).appendChild(style);
  doc.__ncResponsivePreviewLayout = true;
}

function enhancePreviewDocumentForSandbox() {
  let doc;
  try {
    doc = previewFrame?.contentDocument;
  } catch (error) {
    return;
  }
  if (!doc || doc.__ncPreviewEnhanced) return;
  doc.__ncPreviewEnhanced = true;
  applyResponsivePreviewLayout(doc);
  normalizePreviewTables(doc);
  doc.querySelectorAll(".diagram-wrap").forEach((wrap) => {
    if (wrap.querySelector(".diagram-static, .diagram-fallback, .nc-preview-diagram-static")) return;
    const mermaid = wrap.querySelector("pre.mermaid, .mermaid");
    const source = mermaid?.textContent?.trim() || "";
    if (!source) return;
    wrap.appendChild(buildPreviewDiagramFallback(doc, source));
  });
}

function bindPreviewExternalLinks() {
  let doc;
  try {
    doc = previewFrame?.contentDocument;
  } catch (error) {
    return;
  }
  if (!doc || doc.__ncExternalLinksBound) return;
  doc.__ncExternalLinksBound = true;
  doc.addEventListener("click", (event) => {
    const target = event.target?.nodeType === 1 ? event.target : event.target?.parentElement;
    const link = target?.closest?.("a[href]");
    if (!link) return;
    const linkTarget = String(link.getAttribute("target") || "").toLowerCase();
    const href = String(link.href || link.getAttribute("href") || "").trim();
    if (linkTarget !== "_blank" || !/^https?:\/\//i.test(href)) return;
    event.preventDefault();
    event.stopPropagation();
    window.open(href, "_blank", "noopener,noreferrer");
  });
}

function bindPreviewBpmnDownloads() {
  let doc;
  try {
    doc = previewFrame?.contentDocument;
  } catch (error) {
    return;
  }
  if (!doc || doc.__ncBpmnDownloadBound) return;
  doc.__ncBpmnDownloadBound = true;
  doc.addEventListener("click", (event) => {
    const target = event.target?.nodeType === 1 ? event.target : event.target?.parentElement;
    const button = target?.closest?.("[data-bpmn-download]");
    if (!button) return;
    const sourceId = button.getAttribute("data-bpmn-download") || "bpmn-process-xml";
    const source = sourceId ? doc.getElementById(sourceId) : null;
    let xml = "";
    try {
      xml = JSON.parse(source?.textContent || "{}").xml || "";
    } catch (error) {
      xml = "";
    }
    if (!xml) return;
    event.preventDefault();
    event.stopPropagation();
    const fileName = button.getAttribute("data-bpmn-file") || "process.bpmn";
    const blob = new Blob([xml], { type: "application/xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    trackUserEvent("bpmn_xml_downloaded", { selectedName, fileName });
  });
}

function normalizePreviewTables(doc) {
  doc.querySelectorAll("table").forEach((table) => {
    const headers = Array.from(table.querySelectorAll("thead th")).map((cell) => cleanWorkspaceText(cell.textContent));
    if (headers.length === 0) return;
    const signature = headers.join("|");
    if (signature.includes("유즈케이스 ID|액터|유즈케이스명|설명|프로세스 정의 대상")) {
      table.classList.add("nc-preview-usecase-table");
    } else if (signature.includes("상태 코드|상태명|정의|대표 후속 처리")) {
      table.classList.add("nc-preview-state-code-table");
    } else if (
      signature.includes("현재 상태|전이 이벤트|다음 상태|처리 기준 및 후속 처리") ||
      signature.includes("관련 유즈케이스|현재 상태|전이 이벤트|다음 상태|처리 기준 및 후속 처리")
    ) {
      table.classList.add("nc-preview-state-transition-table");
    } else if (signature.includes("프로세스 ID|프로세스명|설명|관련 기능|관련 정책")) {
      table.classList.add("nc-preview-process-table");
    } else if (signature.includes("기능 ID|기능명|설명|세부 기능 구성")) {
      table.classList.add("nc-preview-function-table");
    } else if (signature.includes("정책 ID|정책명|설명|정책 항목")) {
      table.classList.add("nc-preview-policy-table");
    }
  });
}

function buildPreviewDiagramFallback(doc, source) {
  const model = parseMermaidPreviewModel(source);
  const fallback = doc.createElement("div");
  fallback.className = "nc-preview-diagram-static";

  const note = doc.createElement("div");
  note.className = "nc-preview-diagram-note";
  note.textContent = model.kind === "state" ? "상태 전이 미리보기" : "관계 흐름 미리보기";
  fallback.appendChild(note);

  if (model.nodes.length > 0) {
    const nodes = doc.createElement("ul");
    nodes.className = "nc-preview-diagram-nodes";
    model.nodes.slice(0, 18).forEach((label) => {
      const item = doc.createElement("li");
      item.className = "nc-preview-diagram-node";
      item.textContent = label;
      nodes.appendChild(item);
    });
    fallback.appendChild(nodes);
  }

  if (model.edges.length > 0) {
    const edges = doc.createElement("ol");
    edges.className = "nc-preview-diagram-edges";
    model.edges.slice(0, 24).forEach((edge) => {
      const item = doc.createElement("li");
      item.className = "nc-preview-diagram-edge";
      const route = doc.createElement("strong");
      route.textContent = `${edge.from} → ${edge.to}`;
      item.appendChild(route);
      if (edge.label) item.appendChild(doc.createTextNode(` · ${edge.label}`));
      edges.appendChild(item);
    });
    fallback.appendChild(edges);
    return fallback;
  }

  const empty = doc.createElement("div");
  empty.className = "nc-preview-diagram-empty";
  empty.textContent = "다이어그램 원문은 있으나 관계를 자동 해석하지 못했습니다. HTML 다운로드 파일에서는 원본 다이어그램을 확인할 수 있습니다.";
  fallback.appendChild(empty);
  return fallback;
}

function parseMermaidPreviewModel(source) {
  const kind = /^stateDiagram/i.test(source.trim()) ? "state" : "flow";
  const nodeMap = new Map();
  const edges = [];
  const addNode = (id, label) => {
    const cleanId = cleanMermaidLabel(id);
    const cleanLabel = cleanMermaidLabel(label || id);
    if (cleanId && cleanLabel && !nodeMap.has(cleanId)) nodeMap.set(cleanId, cleanLabel);
  };

  source.split(/\r?\n/).forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line || line.startsWith("%%") || /^(classDef|class |style |direction |end\b)/.test(line)) return;

    const stateNode = line.match(/^state\s+"([^"]+)"\s+as\s+([A-Za-z0-9_*[\]-]+)/);
    if (stateNode) {
      addNode(stateNode[2], stateNode[1]);
      return;
    }

    const graphNode = line.match(/^([A-Za-z][\w-]*)\s*(?:\(\[|\[\(|\[\[|\[|\(|\{)\s*"?(.+?)"?\s*(?:\]\)|\)\]|\]\]|\]|\)|\})/);
    if (graphNode) addNode(graphNode[1], graphNode[2]);

    const edge = line.match(/^(\[\*\]|[A-Za-z][\w-]*)\s*(?:-->|---|-.+?->)(?:\|([^|]+)\|)?\s*(\[\*\]|[A-Za-z][\w-]*)(?:\s*:\s*(.+))?/);
    if (edge) {
      addNode(edge[1], edge[1] === "[*]" ? "시작/종료" : edge[1]);
      addNode(edge[3], edge[3] === "[*]" ? "시작/종료" : edge[3]);
      edges.push({
        from: nodeMap.get(cleanMermaidLabel(edge[1])) || cleanMermaidLabel(edge[1]),
        to: nodeMap.get(cleanMermaidLabel(edge[3])) || cleanMermaidLabel(edge[3]),
        label: cleanMermaidLabel(edge[2] || edge[4] || ""),
      });
    }
  });

  return { kind, nodes: [...nodeMap.values()], edges };
}

function cleanMermaidLabel(value) {
  return String(value || "")
    .replace(/&lt;br\/?&gt;|<br\/?>/gi, " ")
    .replace(/["'`]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function installPreviewSelectionHandlers() {
  let doc;
  try {
    doc = previewFrame?.contentDocument;
  } catch (error) {
    return;
  }
  if (!doc || doc.__ncSelectionRevisionInstalled) return;
  doc.__ncSelectionRevisionInstalled = true;
  const captureSoon = (event) => {
    const target = event?.target || null;
    window.setTimeout(() => updateEditorSelectionContextFromSelection(target), 0);
    window.setTimeout(() => capturePreviewSelection(target), 0);
    window.setTimeout(updateEditorToolbarState, 0);
  };
  const captureAfterSelectionSettles = () => {
    window.clearTimeout(doc.__ncSelectionRevisionTimer);
    doc.__ncSelectionRevisionTimer = window.setTimeout(() => {
      updateEditorSelectionContextFromSelection();
      capturePreviewSelection();
      updateEditorToolbarState();
    }, 120);
  };
  doc.addEventListener("click", captureSoon);
  doc.addEventListener("mouseup", captureSoon);
  doc.addEventListener("keyup", captureSoon);
  doc.addEventListener("touchend", captureSoon);
  doc.addEventListener("selectionchange", captureAfterSelectionSettles);
  doc.addEventListener("scroll", hideSelectionRevisionButton, true);
}

function updateEditorSelectionContextFromSelection(fallbackElement = null) {
  if (!workspaceAssistEnabled || (!selectedName && !selectedDraft)) return;
  let doc;
  let selection;
  try {
    doc = previewFrame.contentDocument;
    selection = doc.getSelection();
  } catch (_error) {
    return;
  }
  const anchor = selection && !selection.isCollapsed ? selection.anchorNode : fallbackElement || doc.activeElement || doc.body;
  const element = elementFromSelectionNode(anchor);
  selectedEditorContext = buildSelectedEditorContext(doc, element);
  if (selectedEditorContext) {
    setWorkspaceAssistTab("human");
  }
  renderSelectedElementPanel();
  updateEditorCommentComposer();
}

function buildSelectedEditorContext(doc, element) {
  if (!doc || !element || !doc.body?.contains(element)) return null;
  const block = nearestRevisionBlock(element);
  if (!block) return null;
  const sectionInfo = selectionSectionInfo(doc, element);
  const table = element.closest("table");
  const row = element.closest("tr");
  const cell = element.closest("td, th");
  const tableInfo = detectEditorTableInfo(table);
  const cells = row ? [...row.querySelectorAll("td, th")] : [];
  const elementId = cleanWorkspaceText(cells[0]?.textContent || findNearestPolicyElementId(block));
  const kind = cell || row ? "표 셀/행" : block.tagName?.toLowerCase() === "table" ? "표" : "문단/블록";
  const cellHeader = cell && tableInfo.headers[cells.indexOf(cell)] ? tableInfo.headers[cells.indexOf(cell)] : "";
  const preview = limitClientText(block.innerText || block.textContent || cell?.textContent || "", 260);
  const titleParts = [tableInfo.key !== "generic" ? tableInfo.type : "", cellHeader, elementId].filter(Boolean);
  const context = {
    kind,
    title: titleParts.join(" · ") || sectionInfo.sectionTitle || "선택 요소",
    preview,
    elementId,
    tableType: tableInfo.key !== "generic" ? tableInfo.type : "",
    headingPath: sectionInfo.headingPath,
    traceStatus: elementId ? "ID 감지됨" : "DOM 기준 추정",
  };
  context.targetKey = editorCommentTargetKey(context);
  return context;
}

function findNearestPolicyElementId(element) {
  const text = cleanWorkspaceText(element?.textContent || "");
  const match = text.match(/\b(?:UC|ST|PR|FN|PG)[-_ ]?\d+\b/i);
  return match ? match[0].toUpperCase().replace(/[ _]/g, "-") : "";
}

function capturePreviewSelection(fallbackElement = null) {
  updateEditorSelectionContextFromSelection(fallbackElement);
  if (!selectedName || isEditing || selectedPolicyCompleted()) {
    hideSelectionRevisionButton();
    selectedRevisionTarget = null;
    return;
  }

  let doc;
  let selection;
  try {
    doc = previewFrame.contentDocument;
    selection = doc.getSelection();
  } catch (error) {
    hideSelectionRevisionButton();
    return;
  }

  const selectedText = selection?.toString().trim() || "";
  if (!selection || selection.isCollapsed || selectedText.length < 2) {
    hideSelectionRevisionButton();
    selectedRevisionTarget = null;
    return;
  }

  const range = selection.getRangeAt(0);
  const rect = selectionRevisionAnchorRect(range);
  if (!rect) {
    hideSelectionRevisionButton();
    selectedRevisionTarget = null;
    return;
  }

  const sourceElement = elementFromSelectionNode(range.commonAncestorContainer);
  const sectionInfo = selectionSectionInfo(doc, sourceElement);
  const selectedHtml = htmlFromRange(range);
  const block = nearestRevisionBlock(sourceElement);
  const blockContext = buildSelectedEditorContext(doc, block || sourceElement);
  selectedRevisionTarget = {
    text: limitClientText(selectedText, 1800),
    html: limitClientText(selectedHtml, 6000),
    kind: blockContext?.kind || "선택 영역",
    title: blockContext?.title || sectionInfo.sectionTitle || "선택 영역",
    preview: limitClientText(selectedText, 260),
    blockText: limitClientText(block?.innerText || block?.textContent || selectedText, 2500),
    blockHtml: limitClientText(block?.outerHTML || selectedHtml, 8000),
    sectionTitle: sectionInfo.sectionTitle,
    headingPath: sectionInfo.headingPath,
    elementId: blockContext?.elementId || findNearestPolicyElementId(block),
    tableType: blockContext?.tableType || "",
    traceStatus: blockContext?.traceStatus || "선택 영역 기준",
    targetKey: blockContext?.targetKey || editorCommentTargetKey({
      kind: "선택 영역",
      preview: block?.innerText || block?.textContent || selectedText,
      headingPath: sectionInfo.headingPath,
      elementId: findNearestPolicyElementId(block),
    }),
  };
  positionSelectionRevisionButton(rect);
}

function selectionRevisionAnchorRect(range) {
  const rects = [...range.getClientRects()].filter((rect) => rect.width > 0 && rect.height > 0);
  if (rects.length > 0) {
    const left = Math.min(...rects.map((rect) => rect.left));
    const right = Math.max(...rects.map((rect) => rect.right));
    const top = Math.min(...rects.map((rect) => rect.top));
    const bottom = Math.max(...rects.map((rect) => rect.bottom));
    return {
      left,
      right,
      top,
      bottom,
      width: right - left,
      height: bottom - top,
    };
  }
  const rect = range.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0 ? rect : null;
}

function elementFromSelectionNode(node) {
  if (!node) return null;
  return node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
}

function selectionSectionInfo(doc, element) {
  if (!element) {
    return { sectionTitle: "선택 영역", headingPath: [] };
  }
  const headings = [...doc.querySelectorAll("h2, h3, h4")];
  let h2 = "";
  let h3 = "";
  let h4 = "";
  for (const heading of headings) {
    if (heading === element || heading.contains(element) || heading.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_FOLLOWING) {
      const text = heading.textContent.trim();
      if (heading.tagName === "H2") {
        h2 = text;
        h3 = "";
        h4 = "";
      } else if (heading.tagName === "H3") {
        h3 = text;
        h4 = "";
      } else if (heading.tagName === "H4") {
        h4 = text;
      }
    }
  }
  const path = [h2, h3, h4].filter(Boolean);
  return {
    sectionTitle: path[path.length - 1] || h2 || "선택 영역",
    headingPath: path,
  };
}

function htmlFromRange(range) {
  const wrapper = document.createElement("div");
  wrapper.appendChild(range.cloneContents());
  return wrapper.innerHTML.trim();
}

function nearestRevisionBlock(element) {
  if (!element) return null;
  const blockSelector = "tr, p, li, h1, h2, h3, h4, .diagram-wrap";
  const closest = element.closest(blockSelector);
  if (closest) return closest;
  if (element.matches?.("table")) return element.querySelector("tr") || element;
  return element.querySelector?.(blockSelector) || element.closest("table") || element;
}

function clampToViewport(value, min, max) {
  if (max < min) return min;
  return Math.max(min, Math.min(max, value));
}

function positionSelectionRevisionButton(rangeRect) {
  if (!selectionRevisionButton) return;
  if (!canCurrentUserWritePolicies()) {
    hideSelectionRevisionButton();
    return;
  }
  const frameRect = previewFrame.getBoundingClientRect();
  const margin = 14;
  const gap = 8;
  const anchorX = frameRect.left + rangeRect.left + rangeRect.width / 2;
  const anchorBottom = frameRect.top + rangeRect.bottom;
  const anchorTop = frameRect.top + rangeRect.top;

  if (selectionRevisionButton.hidden && selectionInlineRequest) selectionInlineRequest.value = "";
  if (selectionInlineAiButton) selectionInlineAiButton.disabled = false;
  if (selectionInlineCommentButton) selectionInlineCommentButton.disabled = false;
  selectionRevisionButton.style.visibility = "hidden";
  selectionRevisionButton.hidden = false;
  const buttonWidth = Math.max(280, selectionRevisionButton.offsetWidth || 300);
  const buttonHeight = Math.max(88, selectionRevisionButton.offsetHeight || 92);
  const maxLeft = window.innerWidth - buttonWidth - margin;
  const maxTop = window.innerHeight - buttonHeight - margin;

  let left = anchorX - buttonWidth / 2;
  let top = anchorBottom + gap;
  if (top > maxTop) top = anchorTop - buttonHeight - gap;

  left = clampToViewport(left, margin, maxLeft);
  top = clampToViewport(top, margin, maxTop);
  selectionRevisionButton.style.left = `${left}px`;
  selectionRevisionButton.style.top = `${top}px`;
  selectionRevisionButton.style.visibility = "";
  selectionRevisionButton.hidden = false;
}

function hideSelectionRevisionButton() {
  if (selectionRevisionButton) selectionRevisionButton.hidden = true;
  if (selectionInlineRequest) selectionInlineRequest.value = "";
  if (selectionInlineAiButton) selectionInlineAiButton.disabled = false;
  if (selectionInlineCommentButton) selectionInlineCommentButton.disabled = false;
}

function clearPreviewSelection() {
  hideSelectionRevisionButton();
  selectedRevisionTarget = null;
  try {
    previewFrame.contentDocument?.getSelection()?.removeAllRanges();
  } catch (error) {
    // 선택 영역 초기화는 보조 동작이라 접근 실패 시 무시한다.
  }
}

function openSelectionRevisionModal() {
  if (!selectedRevisionTarget) {
    setMessage("수정할 문서 영역을 먼저 드래그해서 선택해 주세요.", true);
    return;
  }
  hideSelectionRevisionButton();
  selectionRevisionSection.textContent = selectedRevisionTarget.headingPath?.length
    ? `선택 위치: ${selectedRevisionTarget.headingPath.join(" > ")}`
    : "선택한 영역을 기준으로 Agent가 수정합니다.";
  selectionRevisionExcerpt.textContent = selectedRevisionTarget.text;
  selectionRevisionRequest.value = "";
  selectionRevisionModeInputs.forEach((input) => {
    input.checked = input.value === "suggestion";
  });
  updateSelectionRevisionSubmitLabel();
  selectionRevisionModal.hidden = false;
  selectionRevisionRequest.focus();
}

function closeSelectionRevisionModal() {
  if (selectionRevisionModal) selectionRevisionModal.hidden = true;
  if (selectionRevisionRequest) selectionRevisionRequest.value = "";
  if (selectionRevisionSubmitButton) selectionRevisionSubmitButton.disabled = false;
}

function limitClientText(value, limit) {
  const text = String(value || "").trim();
  return text.length > limit ? `${text.slice(0, limit).trim()}...` : text;
}

function setMessage(text, isError = false) {
  message.textContent = text;
  message.classList.toggle("error", isError);
  if (isError && text) {
    trackUserEvent("ui_error", {
      message: limitClientText(text, 600),
      selectedName,
      activeJobId,
    });
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "-";
  const raw = String(value).trim();
  const normalized = raw.includes("T") ? raw : raw.replace(" ", "T");
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized);
  if (hasTimezone) {
    const date = new Date(normalized);
    if (!Number.isNaN(date.getTime())) {
      return formatKoreanTime(date);
    }
  }
  return raw.replace("T", " ").replace(/\.\d+$/, "");
}

function formatKoreanTime(date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const part = (type) => parts.find((item) => item.type === type)?.value || "";
  return `${part("year")}-${part("month")}-${part("day")} ${part("hour")}:${part("minute")}:${part("second")}`;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("ko-KR");
}

function formatCompactNumber(value) {
  const number = Number(value || 0);
  if (number >= 1000000) return `${(number / 1000000).toFixed(number >= 10000000 ? 0 : 1)}M`;
  if (number >= 1000) return `${(number / 1000).toFixed(number >= 10000 ? 0 : 1)}K`;
  return formatNumber(number);
}

function formatUsdCost(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  if (number <= 0) return "$0.00";
  if (number < 0.01) return `$${number.toFixed(4)}`;
  if (number < 1000) return `$${number.toFixed(2)}`;
  return `$${number.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function formatSize(size) {
  const number = Number(size);
  if (!Number.isFinite(number) || number < 0) return "-";
  if (number < 1024) return `${Math.round(number)} B`;
  if (number < 1024 ** 2) return `${Math.round(number / 1024)} KB`;
  if (number < 1024 ** 3) {
    return `${(number / (1024 ** 2)).toFixed(number >= 100 * 1024 ** 2 ? 0 : 1)} MB`;
  }
  return `${(number / (1024 ** 3)).toFixed(number >= 100 * 1024 ** 3 ? 0 : 1)} GB`;
}

function formatDuration(milliseconds) {
  const totalSeconds = Math.max(0, Math.floor(Number(milliseconds || 0) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function formatSeconds(value) {
  const totalSeconds = Math.max(0, Math.floor(Number(value || 0)));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    return `${hours}시간 ${minutes % 60}분`;
  }
  if (minutes > 0) return `${minutes}분 ${seconds}초`;
  return `${seconds}초`;
}

function normalizeTopic(value) {
  return String(value)
    .normalize("NFC")
    .replace(/\s+/g, "")
    .replace(/[^\w가-힣]/g, "");
}

function resolveTopicOptionValue(topic = "") {
  const rawTopic = String(topic || "").trim();
  if (!rawTopic || !topicSelect) return rawTopic;
  const options = [...topicSelect.options].filter((option) => option.value && !option.disabled);
  const exactMatch = options.find((option) => option.value === rawTopic);
  if (exactMatch) return exactMatch.value;
  const normalizedTopic = normalizeTopic(rawTopic);
  const normalizedMatch = options.find((option) => normalizeTopic(option.value) === normalizedTopic);
  return normalizedMatch?.value || rawTopic;
}

function setTopicSelectValue(topic = "", options = {}) {
  if (!topicSelect) return "";
  const resolvedTopic = resolveTopicOptionValue(topic);
  topicSelect.value = resolvedTopic;
  if (topicSelect.value !== resolvedTopic && resolvedTopic) {
    const transientOption = document.createElement("option");
    transientOption.value = resolvedTopic;
    transientOption.textContent = resolvedTopic;
    transientOption.dataset.transient = "true";
    topicSelect.appendChild(transientOption);
    topicSelect.value = resolvedTopic;
  }
  if (options.dispatch) {
    topicSelect.dispatchEvent(new Event("change", { bubbles: true }));
  }
  return topicSelect.value;
}

function getCurrentRequestTopic(formData = null) {
  const rawTopic = String(formData?.get?.("topic") || topicSelect?.value || "").trim();
  const fallbackTopic = rewriteRequestTopic && !rawTopic ? rewriteRequestTopic : rawTopic;
  const resolvedTopic = resolveTopicOptionValue(fallbackTopic);
  if (topicSelect && resolvedTopic && topicSelect.value !== resolvedTopic) {
    setTopicSelectValue(resolvedTopic);
  }
  return String(resolvedTopic || "").trim();
}

function getTopicOptions() {
  const orderedTopics = [];
  const seen = new Set();

  const pushTopic = (value) => {
    const topic = String(value || "").trim();
    if (!topic) return;
    const key = normalizeTopic(topic);
    if (!key || seen.has(key)) return;
    seen.add(key);
    orderedTopics.push(topic);
  };

  if (topicSelect) {
    [...topicSelect.options]
      .filter((option) => option.value && !option.disabled)
      .forEach((option) => pushTopic(option.value));
  }

  currentItems.forEach((item) => pushTopic(item?.topic));
  currentDrafts.forEach((draft) => pushTopic(draft?.topic));
  return orderedTopics;
}

function renderTopicChips(query = "") {
  if (!topicChips || !topicSelect) return;
  const normalizedQuery = normalizeTopic(query);
  const topics = getTopicOptions();
  const matches = normalizedQuery
    ? topics.filter((topic) => normalizeTopic(topic).includes(normalizedQuery))
    : topics;
  const visibleTopics = matches.slice(0, normalizedQuery ? 48 : 18);

  if (visibleTopics.length === 0) {
    topicChips.innerHTML = '<div class="topic-empty">일치하는 주제가 없습니다. 드롭다운에서 직접 선택해 주세요.</div>';
    return;
  }

  topicChips.innerHTML = visibleTopics
    .map((topic) => `
      <button class="topic-chip${normalizeTopic(topicSelect.value) === normalizeTopic(topic) ? " active" : ""}" type="button" data-topic="${escapeHtml(topic)}">
        ${escapeHtml(topic)}
      </button>
    `)
    .join("");

  topicChips.querySelectorAll(".topic-chip").forEach((button) => {
    button.addEventListener("click", () => {
      setTopicSelectValue(button.dataset.topic || "", { dispatch: true });
      renderTopicChips(topicSearch?.value || "");
    });
  });
}

setSideNavCollapsed(sideNavCollapsed);
setWorkspaceAssistTab(activeWorkspaceAssistTab);
setWorkspaceAssistEnabled(workspaceAssistEnabled);
initializeAccessGate();
