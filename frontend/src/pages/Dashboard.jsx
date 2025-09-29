import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

function Dashboard() {
  const [workspaces, setWorkspaces] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API_BASE}/workspaces`)
      .then(response => {
        setWorkspaces(response.data);
        setLoading(false);
      })
      .catch(error => {
        console.error('Error fetching workspaces:', error);
        setLoading(false);
      });
  }, []);

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Workspaces</h2>
      {loading ? (
        <p>Loading...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {workspaces.map(workspace => (
            <div key={workspace.id} className="bg-white p-4 rounded shadow">
              <h3 className="text-lg font-medium">{workspace.name}</h3>
              <Link to={`/workspace/${workspace.id}`} className="text-blue-500 hover:underline">
                View Jobs
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Dashboard;