import { Route, Routes, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { HomePage } from "../pages/HomePage";
import { ProjectsPage } from "../pages/ProjectsPage";
import { ProjectPage } from "../pages/ProjectPage";
import { ApplicationsPage } from "../pages/ApplicationsPage";
import { BooksPage } from "../pages/BooksPage";
import { ActivityPage } from "../pages/ActivityPage";
import { SettingsPage } from "../pages/SettingsPage";
import { InboxPage } from "../pages/InboxPage";
import { SearchPage } from "../pages/SearchPage";
import { IntegrationsPage } from "../pages/IntegrationsPage";
import { IntegrationWorkspacePage } from "../pages/IntegrationWorkspacePage";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="inbox" element={<InboxPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="next" element={<IntegrationWorkspacePage appId="next" />} />
        <Route path="work" element={<IntegrationWorkspacePage appId="work" />} />
        <Route path="cocoder" element={<IntegrationWorkspacePage appId="cocoder" />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="projects/:projectId" element={<ProjectPage />} />
        <Route path="applications" element={<ApplicationsPage />} />
        <Route path="books" element={<BooksPage />} />
        <Route path="activity" element={<ActivityPage />} />
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
