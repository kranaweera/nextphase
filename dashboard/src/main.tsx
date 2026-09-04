import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import App from "./App";
import Alerts from "./pages/Alerts";
import Overview from "./pages/Overview";
import SessionDetail from "./pages/SessionDetail";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Overview />} />
          <Route path="sessions/:sessionId" element={<SessionDetail />} />
          <Route path="alerts" element={<Alerts />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
