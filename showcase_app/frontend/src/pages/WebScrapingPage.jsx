import React, { useState } from 'react';
import { Globe, Search, FileText, Code, Zap, Play, Download, ExternalLink } from 'lucide-react';

/**
 * Web Scraping Tools Page
 * Demonstrates web scraping capabilities with content extraction
 */
export default function WebScrapingPage() {
  const [activeTab, setActiveTab] = useState('single');
  const [singleUrl, setSingleUrl] = useState('https://en.wikipedia.org/wiki/Web_scraping');
  const [batchUrls, setBatchUrls] = useState([
    'https://en.wikipedia.org/wiki/Web_scraping',
    'https://en.wikipedia.org/wiki/Data_mining'
  ]);
  const [scrapingResults, setScrapingResults] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSingleScrape = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/web-scraper/scrape', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: singleUrl,
          extract_text: true,
          include_html: false,
          follow_redirects: true
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      setScrapingResults(result);
    } catch (err) {
      setError(err.message);
      setScrapingResults(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleBatchScrape = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/web-scraper/scrape-batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          urls: batchUrls.filter(url => url.trim()),
          extract_text: true,
          include_html: false,
          max_concurrent: 3
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      setScrapingResults(result);
    } catch (err) {
      setError(err.message);
      setScrapingResults(null);
    } finally {
      setIsLoading(false);
    }
  };

  const addBatchUrl = () => {
    setBatchUrls([...batchUrls, '']);
  };

  const updateBatchUrl = (index, value) => {
    const newUrls = [...batchUrls];
    newUrls[index] = value;
    setBatchUrls(newUrls);
  };

  const removeBatchUrl = (index) => {
    setBatchUrls(batchUrls.filter((_, i) => i !== index));
  };

  const exportResults = () => {
    if (!scrapingResults) return;

    const dataStr = JSON.stringify(scrapingResults, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);

    const exportFileDefaultName = `scraping-results-${new Date().toISOString().split('T')[0]}.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const tabs = [
    { id: 'single', name: 'Single URL', icon: Globe },
    { id: 'batch', name: 'Batch URLs', icon: FileText },
    { id: 'pipeline', name: 'Pipeline Demo', icon: Zap }
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center space-x-3 mb-4">
            <Globe className="h-8 w-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              Web Scraping Tools
            </h1>
          </div>
          <p className="text-lg text-gray-600 dark:text-gray-300">
            Extract content from websites with advanced text processing and safety features
          </p>
        </div>

        {/* Tabs */}
        <div className="mb-6">
          <div className="border-b border-gray-200 dark:border-gray-700">
            <nav className="-mb-px flex space-x-8">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                  }`}
                >
                  <tab.icon className="h-4 w-4" />
                  <span>{tab.name}</span>
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Input Panel */}
          <div className="space-y-6">
            {activeTab === 'single' && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                  Scrape Single URL
                </h3>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      URL to Scrape
                    </label>
                    <input
                      type="url"
                      value={singleUrl}
                      onChange={(e) => setSingleUrl(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                      placeholder="https://example.com"
                    />
                  </div>

                  <button
                    onClick={handleSingleScrape}
                    disabled={isLoading || !singleUrl.trim()}
                    className="w-full flex justify-center items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isLoading ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                        Scraping...
                      </>
                    ) : (
                      <>
                        <Search className="h-4 w-4 mr-2" />
                        Scrape URL
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {activeTab === 'batch' && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                  Scrape Multiple URLs
                </h3>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      URLs to Scrape
                    </label>
                    <div className="space-y-2">
                      {batchUrls.map((url, index) => (
                        <div key={index} className="flex space-x-2">
                          <input
                            type="url"
                            value={url}
                            onChange={(e) => updateBatchUrl(index, e.target.value)}
                            className="flex-1 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                            placeholder="https://example.com"
                          />
                          {batchUrls.length > 1 && (
                            <button
                              onClick={() => removeBatchUrl(index)}
                              className="px-3 py-2 text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                            >
                              Remove
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                    <button
                      onClick={addBatchUrl}
                      className="mt-2 text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                    >
                      + Add URL
                    </button>
                  </div>

                  <button
                    onClick={handleBatchScrape}
                    disabled={isLoading || !batchUrls.some(url => url.trim())}
                    className="w-full flex justify-center items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isLoading ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                        Scraping...
                      </>
                    ) : (
                      <>
                        <FileText className="h-4 w-4 mr-2" />
                        Scrape URLs
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {activeTab === 'pipeline' && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                  Web Scraping Pipeline Demo
                </h3>

                <div className="space-y-4">
                  <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
                    <div className="flex items-start space-x-3">
                      <Zap className="h-5 w-5 text-blue-600 mt-0.5" />
                      <div>
                        <h4 className="text-sm font-medium text-blue-900 dark:text-blue-100">
                          Pipeline: Web Content Analysis
                        </h4>
                        <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                          This pipeline demonstrates scraping web content, analyzing it with AI, and generating reports.
                        </p>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => window.open('/pipelines/web_scraping_demo', '_blank')}
                    className="w-full flex justify-center items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                  >
                    <Play className="h-4 w-4 mr-2" />
                    Run Pipeline Demo
                  </button>
                </div>
              </div>
            )}

            {/* Error Display */}
            {error && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <Code className="h-5 w-5 text-red-400" />
                  </div>
                  <div className="ml-3">
                    <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
                      Scraping Error
                    </h3>
                    <div className="mt-2 text-sm text-red-700 dark:text-red-300">
                      {error}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Results Panel */}
          <div className="space-y-6">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                  Scraping Results
                </h3>
                {scrapingResults && (
                  <button
                    onClick={exportResults}
                    className="flex items-center px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                  >
                    <Download className="h-4 w-4 mr-1" />
                    Export
                  </button>
                )}
              </div>

              {!scrapingResults ? (
                <div className="text-center py-12">
                  <Globe className="mx-auto h-12 w-12 text-gray-400" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">
                    No results yet
                  </h3>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Scrape a URL to see the results here
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Single Result */}
                  {scrapingResults.data && !Array.isArray(scrapingResults.data) && (
                    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1">
                          <h4 className="text-sm font-medium text-gray-900 dark:text-white truncate">
                            {scrapingResults.data.title || 'Untitled Page'}
                          </h4>
                          <a
                            href={scrapingResults.data.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 flex items-center mt-1"
                          >
                            {scrapingResults.data.url}
                            <ExternalLink className="h-3 w-3 ml-1" />
                          </a>
                        </div>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          scrapingResults.data.success
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                            : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                        }`}>
                          {scrapingResults.data.success ? 'Success' : 'Failed'}
                        </span>
                      </div>

                      {scrapingResults.data.success && scrapingResults.data.text_content && (
                        <div className="mt-3">
                          <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-6">
                            {scrapingResults.data.text_content.substring(0, 500)}...
                          </p>
                          <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                            {scrapingResults.data.text_content.length} characters extracted
                          </div>
                        </div>
                      )}

                      {scrapingResults.data.error_message && (
                        <div className="mt-3 text-sm text-red-600 dark:text-red-400">
                          {scrapingResults.data.error_message}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Batch Results */}
                  {scrapingResults.data && Array.isArray(scrapingResults.data) && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between text-sm text-gray-600 dark:text-gray-400">
                        <span>{scrapingResults.successful_scrapes} of {scrapingResults.total_urls} successful</span>
                        <span>{scrapingResults.execution_time?.toFixed(2)}s</span>
                      </div>

                      {scrapingResults.data.map((result, index) => (
                        <div key={index} className="border border-gray-200 dark:border-gray-700 rounded-lg p-3">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex-1 min-w-0">
                              <h5 className="text-sm font-medium text-gray-900 dark:text-white truncate">
                                {result.title || 'Untitled Page'}
                              </h5>
                              <a
                                href={result.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 flex items-center mt-1"
                              >
                                <span className="truncate">{result.url}</span>
                                <ExternalLink className="h-3 w-3 ml-1 flex-shrink-0" />
                              </a>
                            </div>
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ml-2 flex-shrink-0 ${
                              result.success
                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                            }`}>
                              {result.success ? 'Success' : 'Failed'}
                            </span>
                          </div>

                          {result.success && result.text_content && (
                            <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-3 mt-2">
                              {result.text_content.substring(0, 200)}...
                            </p>
                          )}

                          {result.error_message && (
                            <div className="mt-2 text-xs text-red-600 dark:text-red-400">
                              {result.error_message}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}