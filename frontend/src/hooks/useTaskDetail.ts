import { useState, useEffect, useCallback } from 'react';
import { taskApi } from '../services/api';
import type { Task, TaskResults, Nest, TaskImage } from '../types/task';

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

  const refetch = useCallback(async () => {
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
  }, [id]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { task, results, nests, images, loading, error, refetch };
}
