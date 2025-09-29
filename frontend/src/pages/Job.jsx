import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

function Job() {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API_BASE}/jobs/${jobId}`)
      .then(response => {
        setJob(response.data);
        setLoading(false);
      })
      .catch(error => {
        console.error('Error fetching job:', error);
        setLoading(false);
      });
  }, [jobId]);

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Job Details</h2>
      {loading ? (
        <p>Loading...</p>
      ) : job ? (
        <div className="bg-white p-4 rounded shadow">
          <p><strong>ID:</strong> {job.job_id}</p>
          <p><strong>Status:</strong> {job.status}</p>
          <p><strong>Module:</strong> {job.module}</p>
          <p><strong>Target:</strong> {job.target}</p>
          <p><strong>Created:</strong> {job.created_at}</p>
          {job.result && (
            <div className="mt-4">
              <h3 className="text-lg font-medium">Results</h3>
              <pre className="bg-gray-100 p-2 rounded mt-2">{JSON.stringify(job.result, null, 2)}</pre>
              <a href={`${API_BASE}/results/${job.job_id}.json`} className="text-blue-500 hover:underline">Download JSON</a>
            </div>
          )}
          {/* Screenshots would be displayed here */}
        </div>
      ) : (
        <p>Job not found</p>
      )}
    </div>
  );
}

export default Job;