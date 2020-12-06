# vim: ts=4:sw=4:et:cc=120
#

import logging

from saq.system import ACESystemInterface, get_system
from saq.system.analysis_tracking import (
    get_root_analysis,
    track_root_analysis,
)
from saq.system.analysis_request import (
        AnalysisRequest, 
        delete_analysis_request,
        get_analysis_request,
        get_analysis_request_by_observable,
        submit_analysis_request,
        track_analysis_request,
)
from saq.system.analysis_module import get_all_analysis_module_types
from saq.system.caching import cache_analysis, get_cached_analysis
from saq.system.exceptions import (
    UnknownAnalysisRequest,
    ExpiredAnalysisRequest,
    UnknownObservableError,
    UnknownRootAnalysisError,
)

def process_analysis_request(ar: AnalysisRequest):
    # need to lock this at the beginning so that nothing else modifies it
    # while we're processing it
    try:
        # TODO how long do we wait?
        with ar.lock(): # NOTE since AnalysisRequest.lock_id returns RootAnalysis.uuid this also locks the root obj
            root = ar.root
            # did we complete a request?
            if ar.is_observable_analysis_result:
                existing_ar = get_analysis_request(ar.id)
                
                # is this analysis request gone?
                if not existing_ar:
                    raise UnknownAnalysisRequest(ar)

                # did the ownership change?
                if existing_ar.owner != ar.owner:
                    raise ExpiredAnalysisRequest(ar)

                # if we don't already have the RootAnalysis then go get it
                if isinstance(root, str):
                    root = get_root_analysis(root)
                    # is it gone?
                    if not root:
                        raise UnknownRootAnalysisError(ar)

                # should we cache these results?
                if ar.is_cachable:
                    cache_analysis(ar.observable, 
                        ar.analysis_module_type, 
                        ar.result)

                # save the analysis results
                observable = root.get_observable(ar.observable)
                if not observable:
                    raise UnknownObservableError(observable)

                observable.add_analysis(ar.result)
                root.save() # <-- why is this needed?

            # if this is a RootAnalysis request make sure it is tracked
            if ar.is_root_analysis_request:
                # TODO is this RootAnalysis valid?
                track_root_analysis(ar.root)

            # for each observable that needs to be analyzed
            for observable in ar.observables:
                for amt in get_all_analysis_module_types():
                    # does this analysis module accept this observable?
                    if not amt.accepts(observable):
                        continue

                    # is this analysis request already completed?
                    if root.analysis_completed(observable, amt):
                        continue

                    # is this analysis request for this RootAnalysis already being tracked?
                    if root.analysis_tracked(observable, amt):
                        continue

                    # is this observable being analyzed for another root analysis?
                    # this could be in another root analysis as well
                    # NOTE if the analysis module does not support caching
                    # then get_analysis_request_by_observable always returns None
                    tracked_ar = get_analysis_request_by_observable(observable, amt)
                    if tracked_ar and tracked_ar != ar:
                        try:
                            with tracked_ar.lock():
                                if get_analysis_request(tracked_ar.id):
                                    # if we can get the AR and lock it it means it's still in a queue waiting
                                    # so we can tell that AR to update the details of this analysis as well when it's done
                                    tracked_ar.append_root(root)
                                    track_analysis_request(tracked_ar)
                                    # now this observable is tracked to the analysis request for the other observable
                                    observable.track_analysis_request(tracked_ar)
                                    continue

                            # the AR was completed before we could lock it
                            # oh well -- it could be in the cache

                        except Exception as e: # TODO what can be thrown here?
                            breakpoint() # XXX
                            pass

                    # is this analysis in the cache?
                    cached_result = get_cached_analysis(observable, amt)
                    if cached_result:
                        logging.debug(f"using cached analysis for {observable} type {amt} in {root}")
                        root.set_analysis(observable, cached_result)
                        root.save()
                        continue

                    # otherwise we need to request it
                    new_ar = AnalysisRequest(root, observable, amt)

                    # we also track the request inside the RootAnalysis object
                    observable.track_analysis_request(new_ar)
                    root.save()

                    # submit the analysis request for processing
                    submit_analysis_request(new_ar)
                    continue
    finally:
        # at this point this AnalysisRequest is no longer needed
        delete_analysis_request(ar)

    # if there were any other RootAnalysis objects waiting for this one, go ahead and process those now
    for root_uuid in ar.additional_roots:
        new_ar = ar.duplicate()
        new_ar.root = get_root_analysis(root_uuid)
        new_ar.additional_roots = []
        track_analysis_request(new_ar)
        process_analysis_request(new_ar)