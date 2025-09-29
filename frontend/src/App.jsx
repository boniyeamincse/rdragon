import { Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Workspace from './pages/Workspace';
import Job from './pages/Job';

function App() {
  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-blue-600 text-white p-4">
        <h1 className="text-2xl font-bold">ReconDragon</h1>
      </header>
      <main className="container mx-auto p-4">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/workspace/:workspaceId" element={<Workspace />} />
          <Route path="/job/:jobId" element={<Job />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
