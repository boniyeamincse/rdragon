import { Link } from 'react-router-dom';

const API_BASE = 'http://localhost:8000';

function JobCard({ job }) {
  // Mock data for demonstration - in real app, calculate from job.result
  const hostCount = job.result ? job.result.total_probes || 0 : 0;
  const scanTime = job.result ? '5m 30s' : 'N/A'; // Mock

  return (
    <div className="bg-white p-4 rounded shadow flex justify-between items-center">
      <div>
        <h3 className="text-lg font-medium">{job.target}</h3>
        <p>Status: {job.status}</p>
        <p>Hosts: {hostCount}</p>
        <p>Scan Time: {scanTime}</p>
      </div>
      <div className="flex space-x-2">
        <Link to={`/job/${job.id}`} className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">
          View Details
        </Link>
        <a href={`${API_BASE}/results/${job.id}.json`} className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600">
          Download JSON
        </a>
      </div>
    </div>
  );
}

export default JobCard;