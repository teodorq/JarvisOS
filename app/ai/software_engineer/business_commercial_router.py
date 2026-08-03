from __future__ import annotations
from typing import Any
class BusinessCommercialRouter:
    READ=("status produkcji i sprzedaży","status b89-b95","status wersji produkcyjnej","status b89","status aktualizacji klientów","status b90","status licencji komercyjnych","status b91","status ochrony dystrybucji","status b92","status paczki klienta","status b93","status gotowości sprzedażowej","status b94","status wydania produkcyjnego","status b95")
    MUTATE=("przygotuj wersję produkcyjną","promuj wersję do kanału pilot","promuj wersję do kanału stable","skanuj kanały aktualizacji klientów","eksportuj katalog aktualizacji klientów","inicjalizuj wystawcę licencji komercyjnych","wystaw demonstracyjną licencję komercyjną","zweryfikuj licencję komercyjną","zbuduj manifest dystrybucji","zweryfikuj manifest dystrybucji","eksportuj paczkę klienta","zweryfikuj paczkę klienta","eksportuj pakiet sprzedażowy","potwierdź przegląd dokumentów sprzedażowych","eksportuj wydanie produkcyjne","zweryfikuj wydanie produkcyjne")
    @classmethod
    def can_handle(cls,command):
        n=' '.join(str(command).casefold().split()); return any(p in n for p in cls.READ+cls.MUTATE)
    def try_handle(self,suite,*,command,operation=''):
        n=' '.join(str(command).casefold().split()); action=self._action(str(operation).casefold(),n)
        if not action: return None
        service=getattr(suite,'business_edition',None); method=self._mapping().get(action)
        if service is None or not method or not callable(getattr(service,method,None)): return {"success":False,"status":"BUSINESS_COMMERCIAL_SERVICE_UNAVAILABLE","operation":"business_commercial_platform","stage":"B89-B95","errors":[f'Brak operacji {action}.']}
        return getattr(service,method)()
    @classmethod
    def _action(cls,operation,n):
        checks=(("suite",("status produkcji i sprzedaży","status b89-b95")),("b89_prepare",("przygotuj wersję produkcyjną",)),("b89_pilot",("promuj wersję do kanału pilot",)),("b89_stable",("promuj wersję do kanału stable",)),("b89_status",("status wersji produkcyjnej","status b89")),("b90_scan",("skanuj kanały aktualizacji klientów",)),("b90_catalog",("eksportuj katalog aktualizacji klientów",)),("b90_status",("status aktualizacji klientów","status b90")),("b91_init",("inicjalizuj wystawcę licencji komercyjnych",)),("b91_issue",("wystaw demonstracyjną licencję komercyjną",)),("b91_verify",("zweryfikuj licencję komercyjną",)),("b91_status",("status licencji komercyjnych","status b91")),("b92_build",("zbuduj manifest dystrybucji",)),("b92_verify",("zweryfikuj manifest dystrybucji",)),("b92_status",("status ochrony dystrybucji","status b92")),("b93_export",("eksportuj paczkę klienta",)),("b93_verify",("zweryfikuj paczkę klienta",)),("b93_status",("status paczki klienta","status b93")),("b94_export",("eksportuj pakiet sprzedażowy",)),("b94_review",("potwierdź przegląd dokumentów sprzedażowych",)),("b94_status",("status gotowości sprzedażowej","status b94")),("b95_export",("eksportuj wydanie produkcyjne",)),("b95_verify",("zweryfikuj wydanie produkcyjne",)),("b95_status",("status wydania produkcyjnego","status b95")))
        for action,phrases in checks:
            if any(p in n for p in phrases): return action
        return operation if operation in cls._mapping() else None
    @staticmethod
    def _mapping(): return {"suite":"commercial_platform_status","b89_prepare":"prepare_production_version","b89_pilot":"promote_production_pilot","b89_stable":"promote_production_stable","b89_status":"production_versioning_status","b90_scan":"scan_customer_update_channels","b90_catalog":"export_customer_update_catalog","b90_status":"customer_update_channels_status","b91_init":"initialize_commercial_license_authority","b91_issue":"issue_demo_commercial_license","b91_verify":"verify_commercial_license","b91_status":"commercial_license_status","b92_build":"build_distribution_manifest","b92_verify":"verify_distribution_manifest","b92_status":"distribution_protection_status","b93_export":"export_customer_deployment","b93_verify":"verify_customer_deployment","b93_status":"customer_deployment_status","b94_export":"export_sales_handoff","b94_review":"acknowledge_sales_owner_review","b94_status":"sales_readiness_status","b95_export":"export_production_release","b95_verify":"verify_production_release","b95_status":"production_release_status"}
