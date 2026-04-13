export const brandName = '亿境自动化平台';
export const brandShortName = 'YJTest';
export const brandTechPrefix = 'YJTest_';
export const brandStoragePrefix = 'yjtest';
export const brandSubtitle = '智能测试自动化工作台';
export const brandHeroCopy = '用更克制、更流畅的方式管理需求、用例、执行与智能协作。';
export const brandRegisterCopy = '加入亿境自动化平台，开始更轻盈的测试协作体验。';
export const brandChatEmptyCopy = `开始与 ${brandName} 的智能助手对话`;
export const brandReleaseRepo = (import.meta.env.VITE_RELEASE_REPO as string | undefined)?.trim() || '';
export const brandReleaseUrl = brandReleaseRepo ? `https://github.com/${brandReleaseRepo}` : '';
export const brandFeatureTags = [
  'AI 智能生成',
  '知识库检索',
  'MCP 工具集成',
  '自动化执行',
  '测试资产管理',
  '多角色协作',
];

export const routeTitleMap: Record<string, string> = {
  Login: '登录',
  Register: '注册',
  Dashboard: '概览',
  ProjectManagement: '项目管理',
  UserManagement: '用户管理',
  OrganizationManagement: '组织管理',
  PermissionManagement: '权限管理',
  TestCaseManagement: '测试用例',
  TestSuiteManagement: '测试套件',
  TestExecutionHistory: '执行历史',
  LlmConfigManagement: '模型配置',
  LangGraphChat: '智能对话',
  KnowledgeManagement: '知识库',
  ApiKeyManagement: 'API Key',
  RemoteMcpConfigManagement: 'MCP 配置',
  RequirementManagement: '需求管理',
  DocumentDetail: '需求详情',
  ReportDetail: '评审报告',
  SkillsManagement: '技能管理',
  TemplateManagement: '模版管理',
  UiAutomation: 'UI 自动化',
  TraceDetail: '执行链路',
  TaskCenter: '任务中心',
};

export function buildDocumentTitle(routeName?: string | symbol | null): string {
  const title = routeName ? routeTitleMap[String(routeName)] : '';
  return title ? `${title} | ${brandName}` : brandName;
}
