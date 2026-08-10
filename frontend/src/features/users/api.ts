import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../services/api';
import type { UserFilters, AssignRolePayload, ResetPasswordPayload, PaginatedUsersResponse } from './types';
import type { User, UserRole } from '../../types';

export const usersKeys = {
  all: ['users'] as const,
  list: (filters?: UserFilters) => [...usersKeys.all, 'list', filters] as const,
  detail: (id: number) => [...usersKeys.all, 'detail', id] as const,
};

export const useUsersList = (filters?: UserFilters) => {
  return useQuery({
    queryKey: usersKeys.list(filters),
    queryFn: async (): Promise<PaginatedUsersResponse> => {
      const params = new URLSearchParams();
      if (filters?.search) params.append('search', filters.search);
      if (filters?.role) params.append('role', filters.role);
      if (filters?.is_active !== undefined) params.append('is_active', String(filters.is_active));
      if (filters?.wilaya) params.append('wilaya', filters.wilaya);

      const res = await apiClient.get<PaginatedUsersResponse>('/accounts/users/', { params });
      return res.data;
    },
  });
};

export const useCreateUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { username: string; email: string; password: string; first_name: string; last_name: string; role: UserRole; phone: string; wilaya: string }) => {
      const res = await apiClient.post<User>('/accounts/users/', data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: usersKeys.all });
      queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
  });
};

export const useUpdateUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<User> }) => {
      const res = await apiClient.patch<User>(`/accounts/users/${id}/`, data);
      return res.data;
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: usersKeys.all });
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      queryClient.setQueryData(usersKeys.detail(variables.id), data);
    },
  });
};

export const useDeleteUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/accounts/users/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: usersKeys.all });
      queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
  });
};

export const useToggleUserStatus = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, is_active }: { id: number; is_active: boolean }) => {
      const res = await apiClient.patch<User>(`/accounts/users/${id}/`, { is_active });
      return res.data;
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: usersKeys.all });
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      queryClient.setQueryData(usersKeys.detail(variables.id), data);
    },
  });
};

export const useResetPassword = () => {
  return useMutation({
    mutationFn: async ({ id, new_password }: { id: number; new_password: string }) => {
      const res = await apiClient.post(`/accounts/users/${id}/reset-password/`, { new_password });
      return res.data;
    },
  });
};

export const useAssignRole = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, role }: { userId: number; role: UserRole }) => {
      const res = await apiClient.post(`/accounts/${userId}/assign-role/`, { role });
      return res.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: usersKeys.detail(variables.userId) });
      queryClient.invalidateQueries({ queryKey: usersKeys.all });
      queryClient.invalidateQueries({ queryKey: ['permissions'] });
      queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
  });
};

export const useRoleHistory = (userId: number) => {
  return useQuery({
    queryKey: ['roleHistory', userId],
    queryFn: async () => {
      const res = await apiClient.get(`/accounts/audit-log/`, {
        params: { user_id: userId, action: 'ASSIGN_ROLE' },
      });
      return res.data;
    },
    enabled: !!userId,
  });
};
