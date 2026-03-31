const fetchIntegrationStatus = async () => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/integrations/${websiteId}/status`
      );
      if (response.ok) {
        const data = await response.json();
        // Map API data to include icon components
        const mapped = (data.integrations || []).map((i: any) => ({
          ...i,
          icon: getIconForIntegration(i.id),
          relevantFor: i.relevantFor || [],
          dataProvided: i.dataProvided || i.description || '',
        }));
        setIntegrations(mapped.length > 0 ? mapped : getDefaultIntegrations());
      } else {
        setIntegrations(getDefaultIntegrations());
      }
    } catch (error) {
      console.error('Error fetching integration status:', error);
      setIntegrations(getDefaultIntegrations());
    } finally {
      setLoading(false);
    }
  };

  const getIconForIntegration = (id: string) => {
    switch (id) {
      case 'google_search_console': return Search;
      case 'google_analytics': return BarChart3;
      case 'shopify': return ShoppingCart;
      case 'wordpress': return Layers;
      default: return Search;
    }
  };
