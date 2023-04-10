def clean_payload(json_data):
    """
    This function remove keys with empty data.
    """
    final_dict = dict()
    for k, v in json_data.items():
        if v or isinstance(v, bool) or v == 0:
            if isinstance(v, dict):
                final_dict[k] = clean_payload(v)
            elif isinstance(v, list):
                new_list = list()
                for i in v:
                    if isinstance(i, dict):
                        new_list.append(clean_payload(i))
                    elif i:
                        new_list.append(i)

                final_dict[k] = new_list
            else:
                final_dict[k] = v

    return final_dict


def closest(lst, n):
    return lst[min(range(len(lst)), key=lambda i: abs(lst[i] - n))]


def get_zone(aws_zone, ibm_zones_number_zone_dict):
    number = ord(aws_zone[-1]) - 96

    if number not in ibm_zones_number_zone_dict:
        number = closest(ibm_zones_number_zone_dict, number)

    return ibm_zones_number_zone_dict[number]
