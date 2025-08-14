import { useLocation } from 'react-router-dom';
import { BellIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';

const pageNames: Record<string, string> = {
  '/': 'Dashboard',
  '/knowledge': 'Knowledge Base',
  '/chat': 'Chat',
  '/monitoring': 'Monitoring',
  '/settings': 'Settings',
};

export function Header() {
  const location = useLocation();
  const pageName = pageNames[location.pathname] || 'AI Agent';

  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{pageName}</h1>
        </div>
        
        <div className="flex items-center space-x-4">
          {/* Search */}
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search..."
              className="pl-10 pr-4 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
          
          {/* Notifications */}
          <button className="relative p-2 text-gray-400 hover:text-gray-600 transition-colors">
            <BellIcon className="w-5 h-5" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
          </button>
        </div>
      </div>
    </header>
  );
}