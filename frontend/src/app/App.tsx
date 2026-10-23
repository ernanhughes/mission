import { Route, Routes, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { HomePage } from "../pages/HomePage";
import { ProjectsPage } from "../pages/ProjectsPage";
import { ProjectPage } from "../pages/ProjectPage";
import { ApplicationsPage } from "../pages/ApplicationsPage";
import { BooksPage } from "../pages/BooksPage";
import { ActivityPage } from "../pages/ActivityPage";
import { SettingsPage } from "../pages/SettingsPage";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
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
