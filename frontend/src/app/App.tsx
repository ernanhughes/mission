import { Route, Routes, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { HomePage } from "../pages/HomePage";
import { ProjectsPage } from "../pages/ProjectsPage";
import { LivingBookPage } from "../pages/LivingBookPage";
import { ProjectPage } from "../pages/ProjectPage";
import { ApplicationsPage } from "../pages/ApplicationsPage";
import { BooksPage } from "../pages/BooksPage";
import { FictionBooksPage } from "../pages/FictionBooksPage";
import { WebsitesPage } from "../pages/WebsitesPage";
import { ActivityPage } from "../pages/ActivityPage";
import { CostPage } from "../pages/CostPage";
import { CultivationPage } from "../pages/CultivationPage";
import { ScriptsPage } from "../pages/ScriptsPage";
import { SettingsPage } from "../pages/SettingsPage";
import { InboxPage } from "../pages/InboxPage";
import { TestsPage } from "../pages/TestsPage";
import { SearchPage } from "../pages/SearchPage";
import { IntegrationsPage } from "../pages/IntegrationsPage";
import { IntegrationWorkspacePage } from "../pages/IntegrationWorkspacePage";
import { InspectPage } from "../pages/InspectPage";
import { WorkflowsPage } from "../pages/WorkflowsPage";
import { WorkflowDetailPage } from "../pages/WorkflowDetailPage";
import { WriterPage } from "../pages/WriterPage";
import { PublishingWorkbenchPage } from "../pages/PublishingWorkbenchPage";
import { BookPublishingPage } from "../pages/BookPublishingPage";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="inbox" element={<InboxPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="tests" element={<TestsPage />} />
        <Route path="next" element={<IntegrationWorkspacePage key="next" appId="next" />} />
        <Route path="work" element={<IntegrationWorkspacePage key="work" appId="work" />} />
        <Route path="cocoder" element={<IntegrationWorkspacePage key="cocoder" appId="cocoder" />} />
        <Route path="workflows" element={<WorkflowsPage />} />
        <Route path="workflows/:workflowId" element={<WorkflowDetailPage />} />
        <Route path="writer" element={<WriterPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="inspect" element={<InspectPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="projects/:projectId" element={<ProjectPage />} />
        <Route path="projects/:projectId/read" element={<LivingBookPage />} />
        <Route path="projects/:projectId/publishing" element={<BookPublishingPage />} />
        <Route path="publishing" element={<PublishingWorkbenchPage />} />
        <Route path="applications" element={<ApplicationsPage />} />
        <Route path="books" element={<BooksPage />} />
        <Route path="fiction-books" element={<FictionBooksPage />} />
        <Route path="websites" element={<WebsitesPage />} />
        <Route path="activity" element={<ActivityPage />} />
        <Route path="cost" element={<CostPage />} />
        <Route path="cultivation" element={<CultivationPage />} />
        <Route path="scripts" element={<ScriptsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route
          path="*"
          element={
            <div className="page not-found">
              <span className="eyebrow">404</span>
              <h1>This panel does not exist</h1>
              <p>Return to the daily workspace.</p>
              <Link className="button button-primary" to="/">
                Go to Today
              </Link>
            </div>
          }
        />
      </Route>
    </Routes>
  );
}
