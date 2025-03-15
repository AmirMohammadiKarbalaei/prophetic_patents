def read():
    import os, csv, itertools, re, sqlite3, urllib2
    import csv
    import itertools
    import re
    import sqlite3

    countlist = []
    ecountlist = []
    patentlist = []
    patentnumbers = []
    abstracts = []
    specifications = []
    claims = []
    exclude = []
    exampleslist = []
    conn = sqlite3.connect("test.db")
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS patents2(patentnumber INTEGER, app_number TEXT, appdate TEXT, appyear TEXT, title TEXT, issuedate INTEGER, issueyear INTEGER, number_of_claims INTEGER, assistantexaminer TEXT, examiner TEXT, inventorname TEXT, inventorcity TEXT, inventorstate TEXT, inventorcountry TEXT, non_us INTEGER, assignee TEXT, assigneecity TEXT, assigneestate TEXT, prioritychain INTEGER, prioritydate INTEGER, priorityyear INTEGER, backcitations INTEGER, speclength INTEGER, firm TEXT, abstract TEXT, specification TEXT, claims TEXT, examples TEXT, prophetic INTEGER, nonprophetic INTEGER, exclude INTEGER, allprophetic INTEGER, someprophetic INTEGER, noprophetic INTEGER, propheticratio INTEGER)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS examples (patentnumber INTEGER, example TEXT, prophetic INTEGER)"
    )
    os.chdir("/Users/J/Dropbox/Fordham/Scholarship/Prophetic Patents/")
    # os.chdir('/app/home/jfreilich1/zip files')
    urllist = []
    getwebsite = "http://patents.reedtech.com/pgrbft.php"
    website = urllib2.urlopen(getwebsite)
    html = website.read()
    startsearch = html.find("pftaps")
    matches = re.findall("pftaps", html)
    endsearch = html.find("01/06/1976")
    html = html[startsearch - 75 : endsearch]
    x = 0
    while x < (len(matches) / 2):
        startsearch = html.find("downloads")
        endsearch = html.find(">pftaps")
        urllist.append(
            "http://patents.reedtech.com/" + html[startsearch : (endsearch - 1)]
        )
        html = html[endsearch + 5 :]
        x = x + 1
    for i in urllist:
        countlist = []
        with open(i[60:79] + ".txt") as f:
            alltext = f.read()
            for i in re.finditer("WKU ", alltext):
                countlist.append(i.start())
            x = 0
            for i in range(len(countlist) - 1):
                text = alltext[countlist[x] : countlist[x + 1]]
                x = x + 1
                patentlist.append(text)
            text = alltext[countlist[x] :]
            patentlist.append(text)
            for i in patentlist:
                ##PATENT NUMBER
                if i[5] == "R":
                    patentnumber = i[5:7] + i[8:13]
                if i[5] == "D":
                    patentnumber = i[5:6] + i[7:13]
                if i[5] == "P":
                    patentnumber = i[5:6] + i[8:13]
                else:
                    patentnumber = i[6:13]

                ##APPLICATION NUMBER
                startsearch = i.find("SRC  ")
                endsearch = i.find("APN  ")
                appnumber = (
                    str("0")
                    + i[startsearch + 5 : startsearch + 6]
                    + "/"
                    + i[endsearch + 5 : endsearch + 11]
                )
                if startsearch == -1:
                    appnumber = "NA"

                ## APPLICATION DATE
                startsearch = i.find("APD  ")
                appdate = i[startsearch + 5 : startsearch + 13]
                if startsearch == -1:
                    appdate = "NA"

                ## APPLICATION YEAR
                appyear = i[startsearch + 5 : startsearch + 9]
                if startsearch == -1:
                    appyear = "NA"

                ## TITLE
                startsearch = i.find("TTL  ")
                endsearch = i.find("ISD  ")
                title = i[startsearch + 5 : endsearch]
                if startsearch == -1:
                    title = "NA"

                ## ISSUE DATE
                issuedate = i[endsearch + 5 : endsearch + 13]
                if startsearch == -1:
                    issuedate = "NA"

                ## ISSUE YEAR
                issueyear = i[endsearch + 5 : endsearch + 9]
                if startsearch == -1:
                    issueyear = "NA"

                ##NUMBER OF CLAIMS
                startsearch = i.find("NCL  ")
                endsearch = i.find("ECL  ")
                number_of_claims = i[startsearch + 5 : endsearch]
                if startsearch == -1:
                    number_of_claims = "NA"

                ## ASSISTANT EXAMINER
                if "EXA  " in i[endsearch : endsearch + 1000]:
                    startsearch = i.find("EXA  ")
                    endsearch = i.find("EXP  ")
                    assistantexaminer = i[startsearch + 5 : endsearch]
                else:
                    assistantexaminer = "NA"

                ## PRIMARY EXAMINER
                startsearch = i.find("EXP  ")
                endsearch = i.find("NDR  ")
                examiner = i[startsearch + 5 : endsearch]
                if startsearch == -1:
                    examiner = "NA"

                ## FIRST INVENTOR NAME
                startsearch = i.find("NAM  ")
                itemp = i[startsearch:]
                if "STR  " in itemp[0:500]:
                    endsearch = i.find("STR  ")
                else:
                    endsearch = i.find("CTY  ")
                inventorname = i[startsearch + 5 : endsearch]
                if startsearch == -1:
                    inventorname = "NA"

                # Branch off foreign applications
                startsearch = i.find("CTY  ")
                i = i[startsearch:]
                if "PRIR" in i[0:1000] and "CNT  " in i[0:1000]:
                    startsearch = i.find("CNT  ")
                    inventorcity = i[5:startsearch]
                    inventorstate = "NA"
                    inventorcountry = i[startsearch + 5 : startsearch + 7]
                    non_us = 1

                else:
                    ## INVENTOR CITY/STATE/COUNTRY
                    startsearch = i.find("STA  ")
                    if startsearch == -1:
                        inventorcity = "NA"
                        inventorstate = "NA"
                        inventorcountry = "NA"
                    inventorcity = i[5:startsearch]
                    inventorstate = i[startsearch + 5 : startsearch + 7]
                    inventorcountry = "US"
                    non_us = 0

                ## ASSIGNEE NAME
                if "ASSG" in i[0:1000] and "NAM  " in i[0:1000]:
                    startsearch = i.find("ASSG")
                    newi = i[startsearch:]
                    startsearch = newi.find("NAM  ")
                    endsearch = newi.find("CTY  ")
                    assignee = newi[startsearch + 5 : endsearch]
                    if "PRIR" in newi[0:1000] and "CNT  " in newi[0:1000]:
                        startsearch = newi.find("CTY  ")
                        endsearch = newi.find("CNT  ")
                        assigneecity = newi[startsearch + 5 : endsearch]
                        assigneestate = newi[endsearch + 5 : endsearch + 7]
                    else:
                        startsearch = newi.find("CTY  ")
                        endsearch = newi.find("STA  ")
                        assigneecity = newi[startsearch + 5 : endsearch]
                        assigneestate = newi[endsearch + 5 : endsearch + 7]

                else:
                    assignee = "NA"
                    assigneecity = "NA"
                    assigneestate = "NA"

                ## PRIORITY DATE
                if "RLAP" in i[0:2000] and "COD  " in i[0:2000]:
                    prioritylist = []
                    prioritydatelist = []
                    startsearch = i.find("PAL  ")
                    newi = i[:startsearch]
                    prioritychain = newi.count("RLAP")
                    for a in range(prioritychain):
                        startsearch = newi.find("RLAP")
                        b = newi[startsearch:]
                        if "APD  " in b:
                            startsearch = b.find("APD  ")
                            prioritydatelist.append(
                                b[startsearch + 5 : startsearch + 13]
                            )
                        newi = b[startsearch:]
                    sortedpriority = sorted(prioritydatelist)
                    prioritydate = sortedpriority[0]
                    priorityyear = prioritydate[0:4]

                else:
                    prioritychain = 0
                    prioritydate = appdate
                    priorityyear = appyear

                ## BACKWARD CITATIONS
                if "UREF" or "FREF" in i[0:2000]:
                    backcitations = i.count("UREF") + i.count("FREF")
                else:
                    backcitations = 0

                ## FILING FIRM
                startsearch = i.find("FRM  ")
                endsearch = i.find("ABST")
                firm = i[startsearch + 5 : endsearch]
                if startsearch == -1:
                    firm = "NA"

                ##ABSTRACT
                startsearch = i.find("PAL  ")
                endsearch = i.find("BSUM")
                abstract = i[startsearch + 5 : endsearch]
                if startsearch == -1:
                    abstract = "NA"

                ##SPECIFICATION
                startsearch = i.find("BSUM")
                endsearch = i.find("STM  ")
                specification = i[startsearch + 9 : endsearch - 5]
                speclength = len(specification)
                if startsearch == -1:
                    specification = "NA"
                    speclength = "NA"

                ##CLAIMS
                startsearch = i.find("NUM  ")
                endsearch = i.find("WKU  ")
                claims = i[startsearch + 12 : endsearch - 4]
                if startsearch == -1:
                    claims = "NA"

                if "PAC  EXAMPLE" in specification:
                    exampleslist = []
                    ecountlist = []
                    propheticchecklist = 0
                    nopropheticchecklist = 0
                    allexamples = "EXAMPLES: "
                    startsearch = specification.find("PAC  EXAMPLE")
                    examples = specification[startsearch:]
                    for a in re.finditer("PAC  EXAMPLE", examples):
                        ecountlist.append(a.start())
                    x = 0
                    for a in range(len(ecountlist) - 1):
                        etext = examples[ecountlist[x] : ecountlist[x + 1]]
                        x = x + 1
                        allexamples = str(allexamples + " " + etext)
                        exampleslist.append(etext)
                    etext = examples[ecountlist[x] :]
                    exclude = 0
                    allexamples = str(allexamples + " " + etext)
                    exampleslist.append(etext)
                    for u in exampleslist:
                        e_patent = patentnumber
                        e_example = u
                        matchesis = (
                            re.findall(" is ", i)
                            + re.findall(" are ", i)
                            + re.findall(" will be ", i)
                        )
                        matcheswas = (
                            re.findall(" was ", i)
                            + re.findall(" were ", i)
                            + re.findall(" have been ", i)
                            + re.findall(" has been ", i)
                        )
                        if len(matcheswas) == 0:
                            if len(matchesis) > 0:
                                e_prophetic = 1
                                propheticchecklist = propheticchecklist + 1
                            else:
                                e_prophetic = 0
                                nopropheticchecklist = nopropheticchecklist + 1
                        else:
                            e_prophetic = 0
                            nopropheticchecklist = nopropheticchecklist + 1
                        c.execute(
                            "INSERT INTO examples (patentnumber, example, prophetic) VALUES (?,?,?)",
                            (e_patent, e_example, e_prophetic),
                        )
                        conn.commit()

                        if propheticchecklist > 0:
                            if nopropheticchecklist == 0:
                                allprophetic = 1
                                someprophetic = 0
                                noprophetic = 0
                                propheticratio = propheticchecklist
                            else:
                                allprophetic = 0
                                someprophetic = 1
                                noprophetic = 0
                                propheticratio = (
                                    propheticchecklist / nopropheticchecklist
                                )
                        else:
                            allprophetic = 0
                            someprophetic = 0
                            noprophetic = 1
                            propheticratio = 0

                else:
                    exclude = 1
                    allexamples = str("0")
                    propheticchecklist = "NA"
                    nopropheticchecklist = "NA"
                    nopropheticratio = "NA"
                    allprophetic = "NA"
                    someprophetic = "NA"
                    noprophetic = "NA"
                    propheticratio = "NA"
                    e_patent = patentnumber
                    e_example = "NA"
                    e_prophetic = "NA"

                c.execute(
                    "INSERT INTO patents2 (patentnumber, app_number, appdate, appyear, title, issuedate, issueyear, number_of_claims, assistantexaminer, examiner, inventorname, inventorcity, inventorstate, inventorcountry, non_us, assignee, assigneecity, assigneestate, prioritychain, prioritydate, priorityyear, backcitations,  speclength, firm, abstract, specification, claims, examples, prophetic, nonprophetic, exclude, allprophetic, someprophetic, noprophetic, propheticratio) VALUES (?,?,?,?,?, ?, ?,?,?,?,?,?,?,?, ?,?,?,?,?,?,?,?, ?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        patentnumber,
                        appnumber,
                        appdate,
                        appyear,
                        title,
                        issuedate,
                        issueyear,
                        number_of_claims,
                        assistantexaminer,
                        examiner,
                        inventorname,
                        inventorcity,
                        inventorstate,
                        inventorcountry,
                        non_us,
                        assignee,
                        assigneecity,
                        assigneestate,
                        prioritychain,
                        prioritydate,
                        priorityyear,
                        backcitations,
                        speclength,
                        firm,
                        abstract,
                        specification,
                        claims,
                        allexamples,
                        propheticchecklist,
                        nopropheticchecklist,
                        exclude,
                        allprophetic,
                        someprophetic,
                        noprophetic,
                        propheticratio,
                    ),
                )
                conn.commit()

    conn.close()
