import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import AppLayout from './layouts/AppLayout';

import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import AdminDashboardPage from './pages/AdminDashboardPage';
import CandidatesPage from './pages/CandidatesPage';
import CandidateFormPage from './pages/CandidateFormPage';
import CandidateDetailPage from './pages/CandidateDetailPage';
import JobsPage from './pages/JobsPage';
import JobFormPage from './pages/JobFormPage';
import InterviewsPage from './pages/InterviewsPage';
import InterviewFormPage from './pages/InterviewFormPage';
import InterviewPlanReviewPage from './pages/InterviewPlanReviewPage';
import MockInterviewSessionPage from './pages/MockInterviewSessionPage';
import OperationsPage from './pages/OperationsPage';
import UserManagementPage from './pages/UserManagementPage';
import CandidateInterviewPage from './pages/CandidateInterviewPage';
import InterviewEvaluationReportPage from './pages/InterviewEvaluationReportPage';

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg-primary)', color: 'var(--text-muted)' }}>
        Authenticating session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function AdminRoute({ children }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg-primary)', color: 'var(--text-muted)' }}>
        Authenticating session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Recruiter visiting Admin route is redirected to Recruiter dashboard
  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}

function RecruiterRoute({ children }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg-primary)', color: 'var(--text-muted)' }}>
        Authenticating session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Admin visiting Recruiter route is redirected to Admin dashboard
  if (isAdmin) {
    return <Navigate to="/admin/dashboard" replace />;
  }

  return children;
}

function PublicRoute({ children }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();

  if (loading) {
    return null;
  }

  if (isAuthenticated) {
    return <Navigate to={isAdmin ? "/admin/dashboard" : "/dashboard"} replace />;
  }

  return children;
}

function RootDashboardRedirect() {
  const { isAdmin } = useAuth();
  return <Navigate to={isAdmin ? "/admin/dashboard" : "/dashboard"} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Login Route */}
          <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
          />

          {/* Public Invitation Registration Route */}
          <Route
            path="/register"
            element={
              <PublicRoute>
                <RegisterPage />
              </PublicRoute>
            }
          />

          {/* Public Candidate Voice Interview Portal (Token-Authenticated) */}
          <Route
            path="/interview/session"
            element={<CandidateInterviewPage />}
          />

          {/* Protected Main Layout */}
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            {/* Root Route Redirects Based on Role */}
            <Route path="/" element={<RootDashboardRedirect />} />

            {/* Admin-Only Routes */}
            <Route
              path="/admin/dashboard"
              element={
                <AdminRoute>
                  <AdminDashboardPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/users"
              element={
                <AdminRoute>
                  <UserManagementPage />
                </AdminRoute>
              }
            />

            {/* Recruiter-Only Routes */}
            <Route
              path="/dashboard"
              element={
                <RecruiterRoute>
                  <DashboardPage />
                </RecruiterRoute>
              }
            />
            
            <Route
              path="/candidates"
              element={
                <RecruiterRoute>
                  <CandidatesPage />
                </RecruiterRoute>
              }
            />
            <Route
              path="/candidates/new"
              element={
                <RecruiterRoute>
                  <CandidateFormPage />
                </RecruiterRoute>
              }
            />
            <Route
              path="/candidates/:id"
              element={
                <RecruiterRoute>
                  <CandidateDetailPage />
                </RecruiterRoute>
              }
            />

            <Route
              path="/jobs"
              element={
                <RecruiterRoute>
                  <JobsPage />
                </RecruiterRoute>
              }
            />
            <Route
              path="/jobs/new"
              element={
                <RecruiterRoute>
                  <JobFormPage />
                </RecruiterRoute>
              }
            />
            <Route
              path="/jobs/:id"
              element={
                <RecruiterRoute>
                  <JobFormPage />
                </RecruiterRoute>
              }
            />

            <Route
              path="/interviews"
              element={
                <RecruiterRoute>
                  <InterviewsPage />
                </RecruiterRoute>
              }
            />
            <Route
              path="/interviews/new"
              element={
                <RecruiterRoute>
                  <InterviewFormPage />
                </RecruiterRoute>
              }
            />
            <Route
              path="/interviews/:id/plan"
              element={
                <RecruiterRoute>
                  <InterviewPlanReviewPage />
                </RecruiterRoute>
              }
            />
            <Route
              path="/interviews/:id/report"
              element={
                <RecruiterRoute>
                  <InterviewEvaluationReportPage />
                </RecruiterRoute>
              }
            />
            <Route
              path="/interviews/:id/session"
              element={
                <RecruiterRoute>
                  <MockInterviewSessionPage />
                </RecruiterRoute>
              }
            />

            <Route
              path="/operations"
              element={
                <RecruiterRoute>
                  <OperationsPage />
                </RecruiterRoute>
              }
            />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<RootDashboardRedirect />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
