import { useState, useMemo } from 'react';

export interface PaginationState {
  page: number;
  pageSize: number;
  total: number;
}

export interface PaginationActions {
  setPage: (page: number) => void;
  setPageSize: (pageSize: number) => void;
  setTotal: (total: number) => void;
  nextPage: () => void;
  previousPage: () => void;
  goToFirstPage: () => void;
  goToLastPage: () => void;
}

export interface PaginationInfo {
  totalPages: number;
  hasNext: boolean;
  hasPrevious: boolean;
  startIndex: number;
  endIndex: number;
  isFirstPage: boolean;
  isLastPage: boolean;
}

export function usePagination(
  initialPage = 1,
  initialPageSize = 20,
  initialTotal = 0
): [PaginationState, PaginationActions, PaginationInfo] {
  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [total, setTotal] = useState(initialTotal);

  const paginationInfo = useMemo((): PaginationInfo => {
    const totalPages = Math.ceil(total / pageSize);
    const hasNext = page < totalPages;
    const hasPrevious = page > 1;
    const startIndex = (page - 1) * pageSize + 1;
    const endIndex = Math.min(page * pageSize, total);
    const isFirstPage = page === 1;
    const isLastPage = page === totalPages;

    return {
      totalPages,
      hasNext,
      hasPrevious,
      startIndex,
      endIndex,
      isFirstPage,
      isLastPage,
    };
  }, [page, pageSize, total]);

  const actions: PaginationActions = {
    setPage: (newPage: number) => {
      const maxPage = Math.ceil(total / pageSize);
      setPage(Math.max(1, Math.min(newPage, maxPage)));
    },
    setPageSize: (newPageSize: number) => {
      setPageSize(newPageSize);
      // Adjust page to maintain roughly the same position
      const currentStartIndex = (page - 1) * pageSize;
      const newPage = Math.floor(currentStartIndex / newPageSize) + 1;
      setPage(Math.max(1, newPage));
    },
    setTotal,
    nextPage: () => {
      if (paginationInfo.hasNext) {
        setPage(page + 1);
      }
    },
    previousPage: () => {
      if (paginationInfo.hasPrevious) {
        setPage(page - 1);
      }
    },
    goToFirstPage: () => setPage(1),
    goToLastPage: () => setPage(paginationInfo.totalPages),
  };

  return [
    { page, pageSize, total },
    actions,
    paginationInfo,
  ];
}