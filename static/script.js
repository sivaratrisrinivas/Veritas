// Veritas Swiss Interface with Enhanced Error Handling
document.addEventListener('DOMContentLoaded', () => {
    const queryInput = document.getElementById('query-input');
    const searchButton = document.getElementById('search-button');
    const resultsContainer = document.getElementById('results-container');
    const loader = document.getElementById('loader');

    // Supported topics
    const SUPPORTED_TOPICS = ['Health', 'Technology', 'Finance'];

    // Determine trust level based on veracity score
    const getTrustLevel = (score) => {
        if (score >= 75) return 'high';
        if (score >= 50) return 'medium';
        return 'low';
    };

    // Format veracity score for display
    const formatScore = (score) => {
        return Math.round(score);
    };

    // Get human-readable trust description
    const getTrustDescription = (score) => {
        if (score >= 85) return 'Highly Credible';
        if (score >= 75) return 'Credible';
        if (score >= 60) return 'Moderately Credible';
        if (score >= 45) return 'Limited Credibility';
        return 'Low Credibility';
    };

    // Animate score counter
    const animateScore = (element, targetScore, duration = 1000) => {
        const startTime = performance.now();
        const startScore = 0;
        
        const updateScore = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease-out animation curve
            const easedProgress = 1 - Math.pow(1 - progress, 3);
            const currentScore = Math.round(startScore + (targetScore - startScore) * easedProgress);
            
            element.textContent = currentScore;
            
            if (progress < 1) {
                requestAnimationFrame(updateScore);
            }
        };
        
        requestAnimationFrame(updateScore);
    };

    // Handle topic suggestion clicks
    const handleTopicSuggestion = (topic) => {
        const suggestions = {
            'Health': 'COVID vaccine effectiveness',
            'Technology': 'artificial intelligence safety',
            'Finance': 'cryptocurrency market trends'
        };
        
        queryInput.value = suggestions[topic] || '';
        queryInput.focus();
        resultsContainer.innerHTML = '';
    };

    // Display enhanced error messages
    const displayError = (error, isTopicError = false) => {
        const errorClass = isTopicError ? 'error topic-error' : 'error';
        
        if (isTopicError) {
            resultsContainer.innerHTML = `
                <div class="${errorClass}">
                    <h3>Topic Not Supported</h3>
                    <p>${error}</p>
                    <p>Try searching for topics in these areas:</p>
                    <div class="suggested-topics">
                        ${SUPPORTED_TOPICS.map(topic => 
                            `<span class="suggested-topic" data-topic="${topic}">${topic}</span>`
                        ).join('')}
                    </div>
                </div>
            `;
            
            // Add click handlers for suggested topics
            resultsContainer.querySelectorAll('.suggested-topic').forEach(topic => {
                topic.addEventListener('click', () => {
                    handleTopicSuggestion(topic.dataset.topic);
                });
            });
        } else {
            resultsContainer.innerHTML = `
                <div class="${errorClass}">
                    <h3>Search Error</h3>
                    <p>Unable to complete search: ${error}</p>
                    <p>Please try again or check your connection.</p>
                </div>
            `;
        }
    };

    // Main search function
    const performSearch = async () => {
        const query = queryInput.value.trim();
        if (!query) {
            queryInput.focus();
            return;
        }

        // Add search state animations
        queryInput.classList.add('searching');
        searchButton.textContent = 'Analyzing...';
        searchButton.disabled = true;
        loader.classList.remove('hidden');
        resultsContainer.innerHTML = '';

        try {
            const response = await fetch(`/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            if (!response.ok) {
                // Handle different types of errors
                if (response.status === 400 && data.error) {
                    // Check if it's a topic restriction error
                    const isTopicError = data.error.includes('optimized for') || data.error.includes('detected as');
                    setTimeout(() => {
                        displayError(data.error, isTopicError);
                    }, 500);
                } else {
                    throw new Error(`Search failed: ${response.status}`);
                }
                return;
            }
            
            // Small delay to let loading animation play
            setTimeout(() => {
                displayResults(data, query);
            }, 800);
            
        } catch (error) {
            console.error('Search error:', error);
            setTimeout(() => {
                displayError(error.message, false);
            }, 500);
        } finally {
            // Reset UI after delay
            setTimeout(() => {
                queryInput.classList.remove('searching');
                searchButton.textContent = 'Analyze';
                searchButton.disabled = false;
                loader.classList.add('hidden');
            }, 1000);
        }
    };

    // Display search results with enhanced animations
    const displayResults = (results, query) => {
        if (!results || results.length === 0) {
            resultsContainer.innerHTML = `
                <div class="error">
                    <h3>No Results Found</h3>
                    <p>No sources found for "${query}". Try a different search term.</p>
                    <div class="suggested-topics">
                        ${SUPPORTED_TOPICS.map(topic => 
                            `<span class="suggested-topic" data-topic="${topic}">${topic}</span>`
                        ).join('')}
                    </div>
                </div>
            `;
            
            // Add click handlers for suggested topics
            resultsContainer.querySelectorAll('.suggested-topic').forEach(topic => {
                topic.addEventListener('click', () => {
                    handleTopicSuggestion(topic.dataset.topic);
                });
            });
            return;
        }

        // Sort results by veracity score (highest first)
        const sortedResults = [...results].sort((a, b) => b.veracityScore - a.veracityScore);

        sortedResults.forEach((result, index) => {
            const trustLevel = getTrustLevel(result.veracityScore);
            const formattedScore = formatScore(result.veracityScore);
            const trustDescription = getTrustDescription(result.veracityScore);
            
            const resultCard = document.createElement('div');
            resultCard.className = `result-card trust-${trustLevel}`;
            
            // Extract domain for cleaner display
            const domain = new URL(result.url).hostname.replace('www.', '');
            
            // Calculate score breakdown percentages - use actual data if available
            const authorityScore = result.authorityScore || Math.round(result.veracityScore * 0.7);
            const citationScore = result.citationScore || Math.round(result.veracityScore * 0.3);
            const authorityPercent = Math.min(Math.round((authorityScore / 100) * 100), 100);
            
            resultCard.innerHTML = `
                <div class="trust-indicator"></div>
                <h3>
                    <a href="${result.url}" target="_blank" rel="noopener noreferrer">
                        ${result.title || 'Untitled'}
                    </a>
                </h3>
                <p class="url">${domain}</p>
                <div class="score-info">
                    <div class="trust-details">
                        <span class="topic">Topic: ${result.topic || 'General'}</span>
                        <span class="trust-label">${trustDescription}</span>
                        <div class="score-breakdown">
                            <div class="score-bar">
                                <div class="score-bar-fill" style="--score-width: ${authorityPercent}%"></div>
                            </div>
                            <span style="font-size: 12px; color: #999;">Authority: ${authorityScore}/100</span>
                        </div>
                    </div>
                    <div class="veracity-score" data-score="${formattedScore}">0</div>
                </div>
            `;
            
            resultsContainer.appendChild(resultCard);
            
            // Animate the score after the card has been added
            setTimeout(() => {
                const scoreElement = resultCard.querySelector('.veracity-score');
                animateScore(scoreElement, formattedScore, 1200);
            }, 800 + (index * 100));
        });

        // Add summary information with animation
        const avgScore = Math.round(
            sortedResults.reduce((sum, r) => sum + r.veracityScore, 0) / sortedResults.length
        );
        
        const detectedTopic = sortedResults[0]?.topic || 'Mixed';
        
        const summaryCard = document.createElement('div');
        summaryCard.className = 'summary-card';
        summaryCard.innerHTML = `
            <div class="summary-content">
                <h3>Analysis Complete</h3>
                <p>
                    ${sortedResults.length} sources analyzed for <strong>${detectedTopic}</strong> • 
                    Average credibility: <span class="avg-score">0</span>/100
                </p>
            </div>
        `;
        
        resultsContainer.appendChild(summaryCard);
        
        // Animate summary score
        setTimeout(() => {
            const avgScoreElement = summaryCard.querySelector('.avg-score');
            animateScore(avgScoreElement, avgScore, 800);
        }, 1500);
    };

    // Enhanced input interactions
    queryInput.addEventListener('input', () => {
        if (queryInput.value.length > 0) {
            searchButton.style.transform = 'scale(1.02)';
        } else {
            searchButton.style.transform = 'scale(1)';
        }
    });

    // Add click handlers for topic tags in header
    document.querySelectorAll('.topic-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            handleTopicSuggestion(tag.textContent);
        });
    });

    // Event listeners
    searchButton.addEventListener('click', performSearch);
    
    queryInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            performSearch();
        }
    });

    // Focus input on page load with subtle animation
    setTimeout(() => {
        queryInput.focus();
    }, 1000);
});