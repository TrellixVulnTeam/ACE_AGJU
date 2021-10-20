// alert management

function get_all_checked_alerts() {
    // returns the list of all checked alert IDs
    var result = Array(); $("input[name^='detail_']").each(function(index) {
        var $this = $(this);
        if ($this.is(":checked")){
            result.push($this.prop("name").replace(/^detail_/, ""));
        } 
    });

    return result;
}

function setup_daterange_pickers() {
    $('.daterange').each(function(index) {
        if ($(this).val() == '') {
            $(this).val(
                moment().subtract(6, "days").startOf('day').format("MM-DD-YYYY HH:mm") + ' - ' +
                moment().format("MM-DD-YYYY HH:mm"));
        }
    });

    $('.daterange').daterangepicker({
        timePicker: true,
        format: 'MM-DD-YYYY HH:mm',
        startDate:  moment().subtract(6, 'days').startOf('day'),
        endDate: moment(),
        ranges: {
           'Today': [moment().startOf('day'), moment().endOf('day')],
           'Yesterday': [moment().subtract(1, 'days').startOf('day'), moment().subtract(1, 'days').endOf('day')],
           'Last 7 Days': [moment().subtract(6, 'days').startOf('day'), moment()],
           'Last 30 Days': [moment().subtract(29, 'days').startOf('day'), moment()],
           'This Month': [moment().startOf('month').startOf('day'), moment()],
           'Last Month': [moment().subtract(1, 'month').startOf('month').startOf('day'), moment().subtract(1, 'month').endOf('month').endOf('day')]
        }
    });
}

$(document).ready(function() {

    document.getElementById("event_time").value = moment().utc().format("YYYY-MM-DD HH:mm:ss");
    document.getElementById("alert_time").value = moment().utc().format("YYYY-MM-DD HH:mm:ss");
    document.getElementById("ownership_time").value = moment().utc().format("YYYY-MM-DD HH:mm:ss");
    document.getElementById("disposition_time").value = moment().utc().format("YYYY-MM-DD HH:mm:ss");
    document.getElementById("contain_time").value = moment().utc().format("YYYY-MM-DD HH:mm:ss");
    document.getElementById("remediation_time").value = moment().utc().format("YYYY-MM-DD HH:mm:ss");

    $("#master_checkbox").change(function(e) {
        $("input[name^='detail_']").prop('checked', $("#master_checkbox").prop('checked'));
    });

    $("#btn-disposition").click(function(e) {
        // compile a list of all the alerts that are checked
        all_alert_uuids = get_all_checked_alerts();
        if (all_alert_uuids.length == 0) {
            // XXX do this on the disposition button
            alert("You must select one or more alerts to disposition.");
            return;
        }

        // add a hidden field to the form
        $("#disposition-form").append('<input type="hidden" name="alert_uuids" value="' + all_alert_uuids.join(",") + '" />');

        // and then allow the form to follow through
    });

    $("#btn-add-to-event").click(function(e) {
        all_alert_uuids = get_all_checked_alerts();
        if (all_alert_uuids.length > 0) {
            $("#event-form").append('<input type="hidden" name="alert_uuids" value="' + all_alert_uuids.join(",") + '" />');
        }
    });

    $("#btn-save-to-event").click(function(e) {
        let all_alert_uuids = get_all_checked_alerts();
        if (all_alert_uuids.length > 0) {
            $("#event-form").append('<input type="hidden" name="alert_uuids" value="' + all_alert_uuids.join(",") + '" />');
            $("#event_disposition").val($("input[name='disposition']:checked").val());
        }

        let comment_value = $("textarea[name='comment']").val()

        if(comment_value !== "") {
            $.ajax({
                dataType: "html",
                type: "post",
                url: 'add_comment',
                traditional: true,
                data: {
                    uuids: all_alert_uuids.join(","),
                    comment: comment_value,
                    redirect: ''
                },
                error: function (jqXHR, textStatus, errorThrown) {
                    alert(jqXHR.responseText);
                }
            });
        }
    });

    $("#btn-realHours").click(function(e) {
        $("#frm-sla_hours").append('<input type="hidden" name="SLA_real-hours" value="1">').submit();
    });

    $("#btn-BusinessHours").click(function(e) {
        $("#frm-sla_hours").append('<input type="hidden" name="SLA_business-hours" value="1">').submit();
    });

    $("#btn-submit-comment").click(function(e) {
        // compile a list of all the alerts that are checked
        all_alert_uuids = get_all_checked_alerts();
        if (all_alert_uuids.length == 0) {
            alert("You must select one or more alerts to disposition.");
            return;
        }

        $("#comment-form").append('<input type="hidden" name="uuids" value="' + all_alert_uuids.join(",") + '" />');
        $("#comment-form").append('<input type="hidden" name="redirect" value="management" />');
        $("#comment-form").submit();
    });

    $("#btn-submit-tags").click(function(e) {
        $("#tag-form").submit();
    });

    $("#tag-form").submit(function(e) {
        // compile a list of all the alerts that are checked
        all_alert_uuids = get_all_checked_alerts();
        if (all_alert_uuids.length == 0) {
            alert("You must select one or more alerts to add tags to.");
            e.preventDefault();
            return;
        }

        $("#tag-form").append('<input type="hidden" name="uuids" value="' + all_alert_uuids.join(",") + '" />');
        $("#tag-form").append('<input type="hidden" name="redirect" value="management" />');
    });
});

$(document).ready(function() {
    $('input[name="event_time"]').datetimepicker({
        timezone: 0,
        showSecond: false,
        dateFormat: 'yy-mm-dd',
        timeFormat: 'HH:mm:ss'
    });
    $('input[name="alert_time"]').datetimepicker({
        timezone: 0,
        showSecond: false,
        dateFormat: 'yy-mm-dd',
        timeFormat: 'HH:mm:ss'
    });
    $('input[name="ownership_time"]').datetimepicker({
        timezone: 0,
        showSecond: false,
        dateFormat: 'yy-mm-dd',
        timeFormat: 'HH:mm:ss'
    });
    $('input[name="disposition_time"]').datetimepicker({
        timezone: 0,
        showSecond: false,
        dateFormat: 'yy-mm-dd',
        timeFormat: 'HH:mm:ss'
    });
    $('input[name="contain_time"]').datetimepicker({
        timezone: 0,
        showSecond: false,
        dateFormat: 'yy-mm-dd',
        timeFormat: 'HH:mm:ss'
    });
    $('input[name="remediation_time"]').datetimepicker({
        timezone: 0,
        showSecond: false,
        dateFormat: 'yy-mm-dd',
        timeFormat: 'HH:mm:ss'
    });

    setup_daterange_pickers();

    $("#btn-take-ownership").click(function(e) {
        all_alert_uuids = get_all_checked_alerts();
        if (all_alert_uuids.length == 0) {
            alert("You must select one or more alerts to disposition.");
            return;
        }

        $.ajax({
            dataType: "html",
            url: 'set_owner',
            traditional: true,
            data: { alert_uuids: all_alert_uuids },
            success: function(data, textStatus, jqXHR) {
                window.location.replace("/ace/manage")
            },
            error: function(jqXHR, textStatus, errorThrown) {
                alert(jqXHR.responseText);
            }
        });
    });

    $("#btn-assign-ownership").click(function(e) {
        all_alert_uuids = get_all_checked_alerts();
        if (all_alert_uuids.length == 0) {
            // XXX do this on the disposition button
            alert("You must select one or more alerts to assign to a user.");
            return;
        }

        // add a hidden field to the form and then submit
        $("#assign-ownership-form").append('<input type="hidden" name="alert_uuids" value="' + all_alert_uuids.join(",") + '" />').submit();
    });

    $('#btn-limit').click(function(e) {
        result = prompt("How many alerts should be displayed at once?", 50);
    });
});

function new_alert_observable_type_changed(index) {
  var type_input = document.getElementById("observables_types_" + index);
  var value_input = document.getElementById("observables_values_" + index);
  if (type_input.value == 'file') {
    if (value_input.type != 'file') {
      value_input.parentNode.removeChild(value_input);
      $('#new_alert_observable_value_' + index).append('<input class="form-control" type="file" name="observables_values_' + index + '" id="observables_values_' + index + '" value="">');
    }
  } else if (value_input.type != 'text') {
    value_input.parentNode.removeChild(value_input);
    $('#new_alert_observable_value_' + index).append('<input class="form-control" type="text" name="observables_values_' + index + '" id="observables_values_' + index + '" value="">');
  }
}

function new_alert_remove_observable(index) {
  var element = document.getElementById("new_alert_observable_" + index);
  element.parentNode.removeChild(element);
}

// gets called when the user clicks on an observable link
function observable_link_clicked(observable_id) {
    $("#frm-filter").append('<input type="checkbox" name="observable_' + observable_id + '" CHECKED>').submit();
}

// gets called when the user clicks on a tag link
function tag_link_clicked(tag_id) {
    $("#frm-filter").append('<input type="checkbox" name="tag_' + tag_id + '" CHECKED>').submit();
}

// reset all filters
function reset_filters() {
    $.ajax({
        dataType: "html",
        url: 'reset_filters',
        data: { },
        success: function(data, textStatus, jqXHR) {
            window.location.replace("/ace/manage")
        },
        error: function(jqXHR, textStatus, errorThrown) {
            alert("DOH: " + textStatus);
        }
    });
}

// adds a filter
function add_filter(name, values) {
    $.ajax({
        dataType: "html",
        url: 'add_filter',
        traditional: true,
        data: { filter: JSON.stringify({"name":name, "values":values}) },
        success: function(data, textStatus, jqXHR) {
            window.location.replace("/ace/manage");
        },
        error: function(jqXHR, textStatus, errorThrown) {
            alert("DOH: " + textStatus);
        }
    });
}

// adds selected filter from filter modal
function apply_filter() {
    filter_settings = {};
    filters = document.getElementsByName("filter_name");
    for (i = 0; i < filters.length; i++) {
        filter_name = filters[i].value;
        if (!(filter_name in filter_settings)) {
            filter_settings[filter_name] = [];
        }
        filter_inputs = $("[name='" + filters[i].id + "_value_" + filter_name + "']");
        if (filter_inputs.length == 1) {
            val = filter_inputs.val();
            if (Array.isArray(val)) {
                filter_settings[filter_name].push(...val);
            } else {
                filter_settings[filter_name].push(val);
            }
        } else {
            val = [];
            filter_inputs.each(function(index) {
                val.push($(this).val());
            });
            filter_settings[filter_name].push(val);
        }
    }

    $.ajax({
        dataType: "html",
        url: 'set_filters',
        traditional: true,
        data: { filters: JSON.stringify(filter_settings) },
        success: function(data, textStatus, jqXHR) {
            window.location.replace("/ace/manage");
        },
        error: function(jqXHR, textStatus, errorThrown) {
            alert("DOH: " + textStatus);
        }
    });

    return false; // prevents form from submitting
}

// removes a filter
function remove_filter(name, index) {
    $.ajax({
        dataType: "html",
        url: 'remove_filter',
        data: { name: name, index: index },
        success: function(data, textStatus, jqXHR) {
            window.location.replace("/ace/manage")
        },
        error: function(jqXHR, textStatus, errorThrown) {
            alert("DOH: " + textStatus);
        }
    });
}

// removes all filters of type name
function remove_filter_category(name) {
    $.ajax({
        dataType: "html",
        url: 'remove_filter_category',
        data: { name: name },
        success: function(data, textStatus, jqXHR) {
            window.location.replace("/ace/manage")
        },
        error: function(jqXHR, textStatus, errorThrown) {
            alert("DOH: " + textStatus);
        }
    });
}

// sets the sort order
function set_sort_filter(name) {
    $.ajax({
        dataType: "html",
        url: 'set_sort_filter',
        data: { name: name },
        success: function(data, textStatus, jqXHR) {
            window.location.replace("/ace/manage")
        },
        error: function(jqXHR, textStatus, errorThrown) {
            alert("DOH: " + textStatus);
        }
    });
}

// sets page offset
function set_page_offset(offset) {
    $.ajax({
        dataType: "html",
        url: 'set_page_offset',
        data: { offset: offset },
        success: function(data, textStatus, jqXHR) {
            window.location.replace("/ace/manage")
        },
        error: function(jqXHR, textStatus, errorThrown) {
            alert("DOH: " + textStatus);
        }
    });
}

// sets page size
function set_page_size(current_size) {
    limit = prompt("Page size", String(current_size));
    if (limit == null) return;
    err = function() {
        alert("error: enter an integer value between 1 and 1000");
    };

    try {
        limit = parseInt(limit);
    } catch (e) {
        alert(e);
        return;
    }

    if (limit < 1 || limit > 1000) {
        err();
        return;
    }

    $.ajax({
        dataType: "html",
        url: 'set_page_size',
        data: { size: limit },
        success: function(data, textStatus, jqXHR) {
            window.location.replace("/ace/manage")
        },
        error: function(jqXHR, textStatus, errorThrown) {
            alert("DOH: " + textStatus);
        }
    });
}

// hides/shows correct filter value input based on filter name selection
function on_filter_changed(filter_name) {
    filters = document.getElementsByName(filter_name.id + "_value_container");
    for (i = 0; i < filters.length; i++) {
        if (filters[i].id == filter_name.id + "_value_container_" + filter_name.value) {
            filters[i].style.display = "block";
        } else {
            filters[i].style.display = "none";
        }
    }
}

function removeElement(id) {
    var elem = document.getElementById(id);
    return elem.parentNode.removeChild(elem);
}

function removeElements(id_starts_with) {
    $('[id^="' + id_starts_with + '"]').remove();
}

// hides/shows correct input options
function toggle_options(input, options_id) {
    if (input.value.length > 1) {
        input.setAttribute('list', options_id)
    } else {
        input.setAttribute('list', null)
    }
}

function new_filter_option() {
  $.ajax({
    dataType: "html",
    url: 'new_filter_option',
    data: {},
    success: function(data, textStatus, jqXHR) {
      $('#filter_modal_body').append(data);
      setup_daterange_pickers()
    },
    error: function(jqXHR, textStatus, errorThrown) {
      alert("DOH: " + textStatus);
    }
  });
}

// gets called when the user clicks on the right triangle button next to each alert
// this loads the observable information for the alerts and allows the user to select one for filtering
function load_alert_observables(alert_uuid) {
    // have we already loaded this?
    var existing_dom_element = $("#alert_observables_" + alert_uuid);
    if (existing_dom_element.length != 0) {
        existing_dom_element.remove();
        return;
    }

    $.ajax({
        dataType: "html",
        url: 'observables',
        data: { alert_uuid: alert_uuid },
        success: function(data, textStatus, jqXHR) {
            $('#alert_row_' + alert_uuid).after('<tr id="alert_observables_' + alert_uuid + '"><td colspan="6">' + data);
        },
        error: function(jqXHR, textStatus, errorThrown) {
            alert("DOH: " + textStatus);
        }
    });
    
}

function toggle_chevron(alert_row_id) {
    let button_state = document.getElementById(alert_row_id).className;
    if (button_state == "glyphicon glyphicon-chevron-down") {
        document.getElementById(alert_row_id).className = "glyphicon glyphicon-chevron-up";
    } else {
        document.getElementById(alert_row_id).className = "glyphicon glyphicon-chevron-down";
    }
}
