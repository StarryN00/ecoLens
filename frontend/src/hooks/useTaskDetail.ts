import { useState, useEffect, useCallback, useRef } from 'react';
import { taskApi } from '../services/api';
import type { Task, TaskResults, Nest, TaskImage } from '../types/task';

const POLL_INTERVAL_MS = 4000;
const ACTIVE_STATUSES = new Set(['uploading', 'processing']);

interface UseTaskDetailResult {
  task: Task | null;
  results: TaskResults | null;
  nests: Nest[];
  images: TaskImage[];
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useTaskDetail(id: string): UseTaskDetailResult {
  const [task, setTask] = useState<Task | null>(null);
  const [results, setResults] = useState<TaskResults | null>(null);
  const [nests, setNests] = useState<Nest[]>([]);
  const [images, setImages] = useState<TaskImage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const taskStatus = task?.status;

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const refetch = useCallback(async () => {
    stopPolling();
    setLoading(true);
    setError(null);
    try {
      const [taskData, resultsData, nestsData, imagesData] = await Promise.all([
        taskApi.getTask(id),
        taskApi.getTaskResults(id).catch(() => null),
        taskApi.getTaskNests(id).catch(() => ({ items: [] })),
        taskApi.getTaskImages(id).catch(() => ({ items: [] })),
      ]);
      setTask(taskData);
      setResults(resultsData);
      setNests(nestsData.items || []);
      setImages(imagesData.items || []);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('获取任务详情失败'));
    } finally {
      setLoading(false);
    }
  }, [id, stopPolling]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  // Poll status while task is in a non-terminal state
  useEffect(() => {
    if (!taskStatus || !ACTIVE_STATUSES.has(taskStatus)) return;

    pollRef.current = setInterval(async () => {
      try {
        const status = await taskApi.getTaskStatus(id);
        setTask(prev => prev ? { ...prev, ...status } : prev);
        if (!ACTIVE_STATUSES.has(status.status)) {
          stopPolling();
          refetch();
        }
      } catch {
        // ignore transient poll errors
      }
    }, POLL_INTERVAL_MS);

    return stopPolling;
  }, [id, taskStatus, stopPolling, refetch]);

  return { task, results, nests, images, loading, error, refetch };
}
